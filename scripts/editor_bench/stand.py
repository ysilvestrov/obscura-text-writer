"""The editor bench stand: the product's own edit_loop on an isolated data folder (#260 part 2).

One synthetic single-scene story per text (a second scene would need the first one's memory); the editor role changes
between loops. Each loop runs with a run budget equal to what is left of the whole test's cap, so Obscura's own accounting
stops a call that would exceed it. Nothing here reads the owner's data.
"""
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(r'C:\tmp\editor-bench')
KEY_NAMES = ('VENICE_API_KEY', 'OPENROUTER_API_KEY')
PASS_LIMIT = 5
PASS_TIMEOUT = 300


def isolated(path) -> Path:
    """The data folder, refused unless it lies under C:\\tmp\\editor-bench."""
    resolved = Path(path).resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f'Тека стенду має бути всередині {ROOT}')
    return resolved


def load_keys(env_file) -> list[str]:
    """Put only the two provider keys from env_file into this process; return the names found (never the values)."""
    from dotenv import dotenv_values
    values = dotenv_values(env_file)
    found = []
    for name in KEY_NAMES:
        if values.get(name):
            os.environ[name] = values[name]
            found.append(name)
    return found


@dataclass(frozen=True)
class Candidate:
    provider: str
    model: str
    response_mode: str = 'json_schema'
    context_tokens: int = 32768
    max_output_tokens: int = 8192
    reasoning_effort: str | None = None  # OpenRouter's reasoning effort (OPENROUTER-REASONING); None keeps the model's default

    @property
    def code(self):
        suffix = f'@reasoning={self.reasoning_effort}' if self.reasoning_effort else ''
        return f'{self.provider}:{self.model}{suffix}'


@dataclass
class PassTiming:
    seconds: float | None = None
    first_token_seconds: float | None = None


class TimedGateway:
    """Delegates to the product gateway and times each stream from the request to its terminal event."""

    def __init__(self, inner, log):
        self._inner, self._log = inner, log

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def stream(self, ctx, cancel):
        timing = PassTiming()
        self._log.append(timing)
        start = time.perf_counter()
        try:
            for event in self._inner.stream(ctx, cancel):
                if timing.first_token_seconds is None and getattr(event, 'type', None) == 'delta':
                    timing.first_token_seconds = round(time.perf_counter() - start, 3)
                yield event
        finally:
            timing.seconds = round(time.perf_counter() - start, 3)


# The same neutral writer's task for every text: the prose editor's context requires a brief.
BRIEF = '{"objective": "Сцена оповідання; зміст і стиль автора зберігаються.", "beats": ["Події сцени"]}'


@dataclass
class Bench:
    repo: object
    limit_usd: str
    stories: dict = field(default_factory=dict)  # text id -> (story id, scene id)


# The rating axis each text stands for (sexual, violence, themes); a rating is required before any generation.
RATINGS = {'N': (0, 0, 0), 'V': (0, 2, 0), 'T': (0, 0, 2), 'S': (2, 0, 0)}


def _confirm_links(repo, story_id, scene_id):
    """VALID-LINKS: the bench text stands for accepted prose on a confirmed brief; the author's verdicts say so."""
    from storygen.domain import now
    from storygen.storage.link_records import LinkVerdict, new_verdict_id, write_verdict
    from storygen.storage.links import scene_links
    states = scene_links(repo.context_view(story_id), scene_id)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for link in ('brief', 'prose'):
            state = states[link]
            if state.status == 'unchecked':
                write_verdict(db, LinkVerdict(id=new_verdict_id(), story_id=story_id, scene_id=scene_id, link=link,
                                              inputs=state.inputs, fingerprint=state.fingerprint, source='author',
                                              outcome='valid', created_at=now()))


def open_bench(data_dir, texts: dict, limit_usd: str, casts: dict | None = None) -> Bench:
    """One story per text: its broken version as accepted prose, a neutral brief and the whole-test budget. A later
    call on the same folder reuses the stories it made (bench.json), so the cap covers every part of the test."""
    import json
    from storygen.billing.models import money
    from storygen.domain import ContentRating, SceneCreate, StoryCreate
    from storygen.storage.repository import Repository
    root = isolated(data_dir)
    repo = Repository(root)
    bench = Bench(repo, limit_usd)
    index = root / 'bench.json'
    if index.exists():
        bench.stories = {k: tuple(v) for k, v in json.loads(index.read_text(encoding='utf-8')).items()}
    for text_id, text in texts.items():
        if text_id in bench.stories:
            # Every loop edits the scene's prose head, so a reused story must hold exactly the text being scored.
            scene_id = bench.stories[text_id][1]
            if repo.read_text(repo.get_scene(scene_id).heads['prose']) != text:
                raise ValueError(f'Текст {text_id} змінився після створення стенду; оцінка не збігалася б із тим, що редагували')
            continue
        story = repo.create_story(StoryCreate(title=f'Editor bench {text_id}'))
        cast = (casts or {}).get(text_id, [])
        scene = repo.create_scene(story.id, SceneCreate(title=text_id, beats='Події сцени', character_ids=[c['id'] for c in cast]))
        if cast:
            # A sexual rating needs the scene's cast with adult ages (rating guard); the cards come from the local text folder.
            cards = [{'schema_version': 2, 'id': c['id'], 'name': c['name'], 'entries': [
                {'id': c['id'] + '0', 'text': 'Вік: ' + str(c['age']), 'availability': 'timeless', 'available_from_scene_id': None,
                 'origin': 'author', 'sources': []}]} for c in cast]
            cards_ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
            repo.publish_story_material(story.id, 'characters_version_id', cards_ref.id, repo.get_story(story.id).revision)
        repo.update_story_rating(story.id, ContentRating(**dict(zip(('sexual', 'violence', 'themes'), RATINGS.get(text_id, (0, 0, 0))))),
                                 repo.get_story(story.id).revision)
        brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
        repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
        ref = repo.save_version(story.id, scene.id, 'manual', text, [])
        repo.set_head(scene.id, 'prose', ref.id, repo.get_scene(scene.id).revision)
        _confirm_links(repo, story.id, scene.id)
        repo.billing('limit', scope='story:' + story.id, limit_nanos=money(limit_usd), expected_revision=0)
        bench.stories[text_id] = (story.id, scene.id)
    index.write_text(json.dumps(bench.stories), encoding='utf-8')
    return bench


def exposure_usd(bench: Bench) -> float:
    """Spent plus reserved across every bench story, by Obscura's own ledger."""
    return sum(bench.repo.billing('summary', scope='story:' + story_id)['exposure_nanos'] for story_id, _ in bench.stories.values()) / 1e9


def configure_editor(bench: Bench, story_id: str, candidate: Candidate):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.providers.models import ProviderSettings, RoleSettings
    provider = ProviderSettings(provider=candidate.provider, model=candidate.model, response_mode=candidate.response_mode,
                                timeout=PASS_TIMEOUT, include_usage=True,
                                venice_disable_thinking=candidate.provider == 'venice',
                                **({'openrouter_reasoning_effort': candidate.reasoning_effort} if candidate.reasoning_effort else {}))
    settings = RoleSettings(provider=provider, temperature=0.2, context_tokens=candidate.context_tokens,
                            max_output_tokens=candidate.max_output_tokens)
    save_role_settings(bench.repo, story_id, 'editor', settings, bench.repo.get_story(story_id).revision)
    # The owner approved these models for the test: the author's consent for a model without uncensored=true.
    from storygen.providers.policy import endpoint
    bench.repo.model_policy('set_consent', role='editor', provider=provider.provider, base_url=endpoint(provider), model=provider.model)


def run_loop(bench: Bench, text_id: str, candidate: Candidate, gateway_factory=None) -> dict:
    """One edit_loop of up to PASS_LIMIT passes through the product's coordinator; counts, timings and the final text."""
    from storygen.generation.worker import RunCoordinator
    from storygen.providers.streaming import build_generation_gateway
    from storygen.run_models import RunRequest
    story_id, scene_id = bench.stories[text_id]
    configure_editor(bench, story_id, candidate)
    timings = []
    factory = gateway_factory or build_generation_gateway
    worker = RunCoordinator(bench.repo, lambda settings: TimedGateway(factory(settings), timings))
    left = max(0.0, float(bench.limit_usd) - exposure_usd(bench))
    run = worker.enqueue(RunRequest(story_id=story_id, scene_id=scene_id, mode='edit_loop', edit_pass_limit=PASS_LIMIT,
                                    edit_workflow='loop', editor_source_head='prose',
                                    editor_source_version_id=bench.repo.get_scene(scene_id).heads['prose'],
                                    budget_limit_usd=f'{left:.6f}'), f'bench-{text_id}-{candidate.code}'[:200])
    started = time.perf_counter()
    try:
        worker._execute(run.id)
    except Exception as exc:  # A stand failure is a result too; nothing is retried.
        return {'text': text_id, 'model': candidate.code, 'state': 'stand_error', 'error': type(exc).__name__}
    final = worker.get_run(run.id)
    passes = [a for a in bench.repo.list_attempts(story_id, run.id) if a.stage == 'edit' and not a.context.get('edit_loop_summary')]
    data = final.editor_loop or {}
    edited = bench.repo.read_text(data['current_version_id']) if data.get('current_version_id') else None
    return {
        'text': text_id, 'model': candidate.code, 'response_mode': candidate.response_mode,
        'state': final.state, 'stop_reason': data.get('stop_reason'), 'error': final.error,
        'loop_seconds': round(time.perf_counter() - started, 3),
        'passes': [{'state': a.state, 'finish_reason': a.finish_reason, 'cost': a.usage.get('cost'),
                    'accounting': {k: v for k, v in (a.context.get('accounting') or {}).items() if k.endswith(('_nanos', 'usd', 'source', 'state'))},
                    'reasoning_tokens': (a.usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),  # None: not reported
                    'output_tokens': a.usage.get('completion_tokens'),
                    'refusal': bool(a.context.get('generation_failure', {}).get('category', '').startswith('refusal')),
                    'failure': (a.context.get('generation_failure') or {}).get('category') or (a.error and 'error'),
                    'seconds': t.seconds, 'first_token_seconds': t.first_token_seconds}
                   for a, t in zip(passes, timings + [PassTiming()] * (len(passes) - len(timings)))],
        'edited': edited,
    }
