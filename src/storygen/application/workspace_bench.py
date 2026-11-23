"""Workspace response benchmark: synthetic story, timings and a content digest.

Only the public Repository API, readiness.preview and storage.material_status
are used; scene selection goes through the web app (fastapi TestClient) on the URLs the
editor requests. The digest covers outputs only (never timings), so a before/after
comparison proves that a speed change did not change results.
"""
import contextlib
import hashlib
import json
import time
from pathlib import Path

from pydantic import BaseModel

from ..authoring.blueprints import get_role_settings, save_role_settings
from ..domain import ContentRating, SceneCreate, StoryCreate
from ..generation.dependencies import save_manual_prose
from ..generation.pipeline import STAGES
from ..storage.material_status import material_status
from ..memory.service import save_scene_memory
from ..providers.models import RoleSettings
from ..run_models import RunRequest
from ..storage.repository import Repository
from ..roles import ROLES

# Package location: src/storygen/application/workspace_bench.py -> repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]
OPERATIONS = ('prepare', *STAGES, 'scene', 'remaining', 'rebuild_memory', 'edit_loop')
SYNTHETIC_TITLE = 'Synthetic workspace bench'
# PERF-001-S05: a separate workload with character cards and memory selection; the plain one keeps its S03 digests.
CAST_TITLE = 'Synthetic workspace bench (cast)'
CAST_CARDS = 8
CAST_ENTRIES = 6
BENCH_RATING = ContentRating(sexual=0, violence=0, themes=0)
# The auditor has no row of its own in the bench: it borrows the editor's provider (MODEL-001), so old bench workdirs stay valid.
BENCH_ROLES = tuple(role for role in ROLES if role != 'auditor')
# Local provider with builtin prompts: readiness stays offline and needs no budget limit. The window is
# wide enough for a 300-scene memory and plan, so preview reaches build_context and returns ready=True.
BENCH_ROLE = dict(provider=dict(provider='local', model='bench-local'), context_tokens=262144,
                  max_output_tokens=4096, max_input_chars=2_000_000)


@contextlib.contextmanager
def _shallow_model_copy(enabled):
    """Only for CLI synthetic-story building (build_story); forbidden in the server: it drops deep copies of every model."""
    original = BaseModel.model_copy
    if enabled:
        BaseModel.model_copy = lambda self, *, update=None, deep=False: original(self, update=update, deep=False)
    try:
        yield
    finally:
        BaseModel.model_copy = original


def build_story(repo: Repository, scenes: int, shallow_copies: bool = False, cast: bool = False) -> str:
    """Create a story with `scenes` scenes, each with a plan, manual prose and memory (one fact per scene).

    shallow_copies swaps pydantic deep copies for shallow ones while the data is written: the baseline
    code pays O(n^2) deep copies per write, which makes a 300-scene build take hours. Only the setup of
    the synthetic data is affected; measure() always runs the real code.

    cast (PERF-001-S05) adds neutral character cards with protagonist, other-name and acquaintance markers, a cast on
    every scene, a hidden memory record and a later edit of the cards, so every prose head is stale.
    """
    with _shallow_model_copy(shallow_copies):
        return _build_story(repo, scenes, cast)


def configure_roles(repo: Repository, story_id: str) -> None:
    """Save the bench roles (planner, writer, editor, memory; the auditor stays derived) so readiness checks the full path."""
    role = RoleSettings.model_validate(BENCH_ROLE)
    for name in BENCH_ROLES:
        save_role_settings(repo, story_id, name, role, repo.get_story(story_id).revision)


def _cast_cards(edition):
    """Neutral cards: card 0 is the protagonist; every card has another name and knows the next card."""
    from ..characters.models import CharacterEntry, CharacterRecord
    cards = []
    for c in range(CAST_CARDS):
        lines = [f'Роль у творі: {"Головна героїня" if c == 0 else "Другорядна роль"}', f"Інше ім'я: Псевдо {c + 1}",
                 f'Знайомий з: Персонаж {(c + 1) % CAST_CARDS + 1}']
        traits = lambda e: [f'- Риса {e}.{k} ({edition})' for k in range(8)]
        entries = [CharacterEntry(id=f'e{c}_{e}', origin='author', availability='timeless',
                                  text='\n'.join((lines if e == 0 else []) + traits(e)))
                   for e in range(CAST_ENTRIES)]
        cards.append(CharacterRecord(id=f'c{c}', name=f'Персонаж {c + 1}', entries=entries))
    return json.dumps([card.model_dump() for card in cards], ensure_ascii=False)


def _publish_cards(repo, story_id, edition):
    ref = repo.save_version(story_id, None, 'character_cards', _cast_cards(edition), [])
    repo.publish_story_material(story_id, 'characters_version_id', ref.id, repo.get_story(story_id).revision)


def _build_story(repo, scenes, cast=False):
    story = repo.create_story(StoryCreate(title=CAST_TITLE if cast else SYNTHETIC_TITLE))
    # Generation is blocked for an unrated story, so the bench rates its own story before anything else.
    story = repo.update_story_rating(story.id, BENCH_RATING, story.revision)
    if cast:
        _publish_cards(repo, story.id, 'first')
    sources, facts = [], []
    for i in range(scenes):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Scene {i + 1}', beats=f'Plan beat {i + 1}'))
        repo.update_scene_plan(scene.id, scene.beats, scene.revision)
        scene = repo.get_scene(scene.id)
        if cast:
            repo.update_scene_metadata(scene.id, {'character_ids': ['c0', f'c{i % (CAST_CARDS - 1) + 1}']}, scene.revision)
            scene = repo.get_scene(scene.id)
        text = f'Synthetic detail number {i + 1}.'
        save_manual_prose(repo, scene.id, text, scene.revision)
        scene = repo.get_scene(scene.id)
        sources.append(scene.heads['prose'])
        facts.append(dict(text=text, source_version_id=sources[-1], quote=text))
        save_scene_memory(repo, scene.id, json.dumps(dict(source_prose_ids=list(sources), facts=list(facts))), scene.revision)
        if cast and i == 0:
            _hide_first_record(repo, scene.id)
    if cast:
        _publish_cards(repo, story.id, 'second')
    # Roles are saved last, so their presence marks a completed build (see _check_synthetic).
    configure_roles(repo, story.id)
    return story.id


def _hide_first_record(repo, scene_id):
    """The author hides the first memory record of the scene, so later scenes have a non-empty projection policy."""
    from ..memory.forwarding import memory_view, save_forwarding
    table = memory_view(repo, scene_id)
    save_forwarding(repo, scene_id, {table['rows'][0]['claim_id']: False}, table['expected_revision'], table['fingerprint'])


def _check_synthetic(repo, story_id, scenes):
    """Refuse to measure a reused synthetic story that is not the requested, completed workload."""
    found = len(repo.context_view(story_id).list_scenes(story_id))
    if found != scenes:
        raise ValueError(f'synthetic_mismatch: workdir story has {found} scenes, requested {scenes}; use a new --workdir')
    roles = get_role_settings(repo, story_id)
    if any(name not in roles for name in BENCH_ROLES):
        raise ValueError('synthetic_incomplete: workdir story has no bench roles (interrupted or old build); '
                         'use a new --workdir')
    if repo.get_story(story_id).content_rating is None:
        raise ValueError('synthetic_unrated: workdir story has no age rating (built before content ratings); '
                         'use a new --workdir')


def _request(story_id, scene_id, name):
    # Mirrors RunCoordinator.readiness: model_construct permits an unselected scene.
    return RunRequest.model_construct(
        story_id=story_id, scene_id=scene_id,
        mode='stage' if name in STAGES else name,
        stage=name if name in STAGES else None,
        edit_workflow='loop' if name in {'scene', 'remaining'} else 'single',
        editor_source_head=None, editor_source_version_id=None)


def _story_view(repo, story_id):
    # Same repository calls as routes_stories.story_view.
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    return {'material_status': material_status(view), 'story': story,
            'scenes': [view.effective_scene(s.id) for s in view.list_scenes(story_id)]}


def _scene_attempts(repo, story_id, scene_id):
    # Same calls and filters as routes_versions.list_copyedit_proposals and routes_rewrites.list_rewrites.
    copyedits = [a.id for a in repo.list_attempts(story_id, scene_id=scene_id, context_key='copyedit_proposal')
                 if a.context.get('copyedit_proposal') and a.state in {'completed', 'needs_review', 'alternative'}]
    rewrites = [a.id for a in repo.list_attempts(story_id, scene_id=scene_id, context_key='rewrite_proposal')
                if a.context.get('rewrite_proposal')]
    return copyedits, rewrites


def _timed(timings, key, fn):
    start = time.perf_counter()
    result = fn()
    timings[key] = timings.get(key, 0.0) + time.perf_counter() - start
    return result


def _default(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json')
    return str(value)


def measure(repo: Repository, story_id: str) -> dict:
    from ..generation.readiness import preview
    repo.get_story(story_id)
    scenes = repo.context_view(story_id).list_scenes(story_id)
    middle = scenes[len(scenes) // 2].id if scenes else None
    timings, outputs = {}, {}
    for name in OPERATIONS:
        outputs['readiness:' + name] = _timed(timings, 'readiness:' + name,
                                              lambda name=name: preview(repo, _request(story_id, middle, name)))

    def readiness_all():
        # Mirrors RunCoordinator.readiness without `operation`: one view for every operation.
        # Timed only; the result stays out of the digest, which fixes the measured operations.
        view = repo.context_view(story_id)
        return [preview(repo, _request(story_id, middle, name), view) for name in OPERATIONS]
    _timed(timings, 'readiness:all', readiness_all)
    outputs['story_view'] = _timed(timings, 'story_view', lambda: _story_view(repo, story_id))
    outputs['attempts'] = _timed(timings, 'list_attempts', lambda: _scene_attempts(repo, story_id, middle))
    runs = _timed(timings, 'list_runs', lambda: repo.list_runs(story_id))
    outputs['run_ids'] = [r.id for r in runs]

    selection = _scene_select(repo, story_id, middle)
    # Server time of the selection requests only; building the app and the client is not part of a click.
    timings['scene_select'] = sum(seconds for _, seconds in selection.values())
    outputs['scene_select'] = {label: response for label, (response, _) in selection.items()}
    # PERF-001-S03 (#39): the requests of opening a story, through the app (and so inside its lineage scope).
    opening = _story_open(repo, story_id)
    timings['story_open'] = sum(seconds for _, seconds in opening.values())
    outputs['story_open'] = {label: response for label, (response, _) in opening.items()}
    return {'story': story_id[:8], 'scenes': len(scenes),
            'timings': {k: round(v, 6) for k, v in timings.items()},
            'scene_select_requests': {label: round(seconds, 6) for label, (_, seconds) in selection.items()},
            'story_open_requests': {label: round(seconds, 6) for label, (_, seconds) in opening.items()},
            'digest': _digest(outputs),
            # Outputs without app requests: comparable with digests taken before scene_select used the web app.
            'digest_core': _digest({k: v for k, v in outputs.items() if k not in {'scene_select', 'story_open'}})}


def _digest(outputs):
    canonical = json.dumps(outputs, sort_keys=True, ensure_ascii=False, default=_default)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _story_open(repo, story_id):
    """The heavy GET requests of opening a story in the editor: the story view and the trash.
    Returns {label: ((status, json), seconds)}; labels carry no ids."""
    return _app_requests(repo, 'story_open_failed', [('story', f'/api/stories/{story_id}'),
                                                     ('trash', f'/api/stories/{story_id}/trash')])


def _app_requests(repo, error, requests):
    from fastapi.testclient import TestClient
    from ..application.settings import AppSettings
    from ..web.app import create_app
    app = create_app(AppSettings(data_dir=repo.root, env_file=repo.root / '.workspace-bench-no.env'))
    client = TestClient(app, base_url='http://127.0.0.1:8765', raise_server_exceptions=False)
    result = {}
    try:
        for label, url in requests:
            start = time.perf_counter()
            response = client.get(url)
            seconds = time.perf_counter() - start
            try:
                body = response.json()
            except ValueError:
                body = None
            if response.status_code >= 500 or body is None:
                raise ValueError(f'{error}: {label} returned HTTP {response.status_code}')
            result[label] = ((response.status_code, body), seconds)
    finally:
        client.close()
    return result


def _scene_select(repo, story_id, scene_id):
    """The GET requests the editor sends after a scene is selected (scene-selected listeners), through the app.

    readiness?operation=brief and /runs (runs.js, plan mode), versions (versions.js), statistics (scene-statistics.js),
    comments (author-comments.js), copyedit and rewrite lists (change-review.js) and evaluator (evaluation.js). The TestClient is not entered as a context
    manager, so the app lifespan (worker start) never runs and nothing is enqueued.
    Returns {label: ((status, json), seconds)}; labels carry no ids.
    """
    from fastapi.testclient import TestClient
    from ..application.settings import AppSettings
    from ..web.app import create_app
    app = create_app(AppSettings(data_dir=repo.root, env_file=repo.root / '.workspace-bench-no.env'))
    # Server exceptions become 500 responses, so one failing endpoint is reported by label, not as a traceback.
    client = TestClient(app, base_url='http://127.0.0.1:8765', raise_server_exceptions=False)
    result = {}

    def get(label, url):
        start = time.perf_counter()
        response = client.get(url)
        seconds = time.perf_counter() - start
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 500 or body is None:
            # Only the label and status: response bodies may quote story text.
            raise ValueError(f'scene_select_failed: {label} returned HTTP {response.status_code}')
        result[label] = ((response.status_code, body), seconds)
        return body if response.status_code == 200 else None
    try:
        get('readiness', f'/api/stories/{story_id}/readiness?scene_id={scene_id}&operation=brief')
        get('runs', f'/api/stories/{story_id}/runs')
        get('versions', f'/api/scenes/{scene_id}/versions')
        get('statistics', f'/api/scenes/{scene_id}/statistics?stage=draft')
        get('comments', f'/api/scenes/{scene_id}/comments')
        get('copyedits', f'/api/scenes/{scene_id}/copyedits')
        get('rewrites', f'/api/scenes/{scene_id}/rewrites')
        get('evaluator', f'/api/stories/{story_id}/evaluator')
    finally:
        client.close()
    return result


def _live_data_dirs():
    """The working data directories: <repo root>/data and, from a git worktree, the main checkout's data."""
    dirs = {(REPO_ROOT / 'data').resolve()}
    marker = REPO_ROOT / '.git'
    if marker.is_file():
        text = marker.read_text(encoding='utf-8', errors='replace').strip()
        if text.startswith('gitdir:'):
            gitdir = Path(text[len('gitdir:'):].strip())
            gitdir = gitdir if gitdir.is_absolute() else REPO_ROOT / gitdir
            # <main>/.git/worktrees/<name> -> <main>/data
            if gitdir.parent.name == 'worktrees':
                dirs.add((gitdir.parent.parent.parent / 'data').resolve())
    return dirs


def _check_data_dir(path, require_database):
    """Refuse the working database and (for --data) a directory that holds no storygen.sqlite3, before any open."""
    resolved = Path(path).resolve()
    if resolved in _live_data_dirs():
        raise ValueError('live_data: refusing to benchmark the working data directory; use a copy')
    if require_database and not (resolved / 'storygen.sqlite3').is_file():
        raise ValueError('not_a_data_copy: --data holds no storygen.sqlite3')
    return resolved


def run(data=None, story=None, synthetic=None, workdir=None, cast=False) -> dict:
    """Open a data directory (or a synthetic workdir, reused only when it holds the same completed workload) and measure."""
    repo = Repository(_check_data_dir(workdir, False) if synthetic else _check_data_dir(data, True))
    if synthetic:
        title = CAST_TITLE if cast else SYNTHETIC_TITLE
        existing = [s for s in repo.list_stories() if s.title == title]
        if len(existing) > 1:
            raise ValueError('synthetic_ambiguous: workdir holds several synthetic stories; use a new --workdir')
        if existing:
            story_id = existing[0].id
            _check_synthetic(repo, story_id, synthetic)
        else:
            story_id = build_story(repo, synthetic, shallow_copies=True, cast=cast)
    else:
        chosen = [s for s in repo.list_stories() if story is None or s.id.startswith(story)]
        if not chosen:
            raise LookupError('story_not_found')
        story_id = chosen[0].id
    return measure(repo, story_id)
