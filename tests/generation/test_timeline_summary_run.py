"""MEMORY-SUMMARY-S05: the timeline_summary run — memory role, block input, validation, CAS and readiness."""
import json

import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.generation.readiness import preview
from storygen.generation.timeline_summary import build_summary_context, validate_summary
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.policy import MULTI_SCENE_STAGES, STAGE_POLICY_ROLE
from storygen.providers.streaming import GenerationEvent
from storygen.run_models import RunRequest
from tests.memory.summary_helpers import long_story

GOOD = 'Анна приїхала до міста, знайшла кімнату біля річки й почала шукати роботу.'


class Gateway:
    def __init__(self, text, before=None):
        self.text, self.before = text, before

    def stream(self, *args):
        if self.before:
            self.before()
        yield GenerationEvent(type='delta', text=self.text)
        yield GenerationEvent(type='terminal', finish_reason='stop', usage={'prompt_tokens': 100, 'completion_tokens': 40})


def seeded(tmp_path, count=12, memory_until=None):
    repo, story = long_story(tmp_path, count, memory_until)
    role = RoleSettings(provider=ProviderSettings(model='memory-test'), context_tokens=128000, max_input_chars=1000000, max_output_tokens=2048)
    save_role_settings(repo, story.id, 'memory', role, story.revision)
    return repo, repo.get_story(story.id)


def run(repo, story, text=GOOD, before=None, key='range:1-10', request_id='summary-1'):
    worker = RunCoordinator(repo, gateway_factory=lambda _: Gateway(text, before))
    request = RunRequest(story_id=story.id, mode='timeline_summary', summary_block_key=key)
    queued = worker.enqueue(request, request_id)
    queued.state = 'running'
    repo.save_run(queued)
    worker._execute(queued.id)
    return worker, repo.get_run(queued.id), repo.list_attempts(story.id, queued.id)[-1]


def test_request_validation():
    with pytest.raises(ValueError, match='Блок підсумку задається лише для підсумку хронології'):
        RunRequest(story_id='s', mode='timeline_summary')
    with pytest.raises(ValueError, match='належить блоку твору, не окремій сцені'):
        RunRequest(story_id='s', scene_id='x', mode='timeline_summary', summary_block_key='range:1-10')
    with pytest.raises(ValueError, match='Блок підсумку задається лише для підсумку хронології'):
        RunRequest(story_id='s', scene_id='x', mode='scene', summary_block_key='range:1-10')
    assert STAGE_POLICY_ROLE['timeline_summary'] == 'memory' and 'timeline_summary' in MULTI_SCENE_STAGES


def test_context_holds_the_block_timeline_not_prose(tmp_path):
    repo, story = seeded(tmp_path)
    context = build_summary_context(repo, story.id, 'range:1-10')
    data = json.loads(context.user_text)
    assert data['timeline'][0].startswith('Сцена 1: Подія сцени 1') and len(data['timeline']) == 10
    assert 'Анна йде містом.' not in context.user_text and data['max_chars'] == 1200
    assert context.settings.provider.model == 'memory-test' and len(context.input_refs) == 10


def test_run_publishes_the_head(tmp_path):
    repo, story = seeded(tmp_path)
    _, finished, attempt = run(repo, story)
    assert finished.state == 'completed' and attempt.state == 'completed'
    head = repo.get_story(story.id).timeline_summary_heads['range:1-10']
    assert head == attempt.result_version_id
    assert json.loads(repo.read_text(head))['text'] == GOOD and json.loads(repo.read_text(head))['origin'] == 'model'


@pytest.mark.parametrize('text,message', [('А' * 1201, '1200'), ('Anna came to the city and found a room by the river.', 'українською'), ('   ', 'порожн')])
def test_invalid_answer_fails_without_publication(tmp_path, text, message):
    repo, story = seeded(tmp_path)
    _, finished, attempt = run(repo, story, text)
    assert attempt.state == 'failed' and message in attempt.error
    assert repo.get_story(story.id).timeline_summary_heads == {}


def test_revision_conflict_leaves_the_version_unpublished(tmp_path):
    from storygen.domain import ContentRating
    repo, story = seeded(tmp_path)
    bump = lambda: repo.update_story_rating(story.id, ContentRating(sexual=1, violence=1, themes=1), repo.get_story(story.id).revision)
    _, finished, attempt = run(repo, story, before=bump)
    assert attempt.state == 'alternative' and attempt.result_version_id
    assert repo.get_story(story.id).timeline_summary_heads == {}


def test_scene_without_memory_is_not_ready_and_not_queued(tmp_path):
    repo, story = seeded(tmp_path, memory_until=9)
    request = RunRequest(story_id=story.id, mode='timeline_summary', summary_block_key='range:1-10')
    result = preview(repo, request)
    assert not result['ready'] and 'Сцена 10' in result['reason']
    with pytest.raises(ValueError, match='Сцена 10'):
        RunCoordinator(repo, gateway_factory=lambda _: Gateway(GOOD)).enqueue(request, 'no-memory')
    assert not repo.list_runs(story.id)


def test_second_run_of_the_same_block_is_refused(tmp_path):
    repo, story = seeded(tmp_path)
    worker = RunCoordinator(repo, gateway_factory=lambda _: Gateway(GOOD))
    request = RunRequest(story_id=story.id, mode='timeline_summary', summary_block_key='range:1-10')
    worker.enqueue(request, 'first')
    with pytest.raises(ValueError, match='вже створюється'):
        worker.enqueue(request, 'second')


def test_ready_preview_names_the_memory_role(tmp_path):
    repo, story = seeded(tmp_path)
    result = preview(repo, RunRequest(story_id=story.id, mode='timeline_summary', summary_block_key='range:1-10'))
    assert result['ready'] and result['calls'] == 1 and result['roles']['memory']['model'] == 'memory-test'


def test_rating_of_any_block_scene_blocks_the_store_edition(tmp_path, monkeypatch):
    from storygen import build_edition
    from storygen.domain import ContentRating
    repo, story = seeded(tmp_path)
    scene = repo.list_scenes(story.id)[4]
    repo.update_scene_rating(scene.id, ContentRating(sexual=2, violence=0, themes=0), repo.get_scene(scene.id).revision)
    build_summary_context(repo, story.id, 'range:1-10')
    edition = build_edition.BuildEdition(edition='store', report_url='https://example.test/report')
    monkeypatch.setattr(build_edition, 'current', lambda: edition)
    with pytest.raises(ValueError, match='Генерацію заблоковано: рейтинг «сексуальний зміст» тут 2'):
        build_summary_context(repo, story.id, 'range:1-10')


def test_validate_summary_language():
    assert validate_summary('  ' + GOOD + ' ', 1200, 'uk') == GOOD
    assert validate_summary('Anna came to the city.', 1200, 'en') == 'Anna came to the city.'
    with pytest.raises(ValueError, match='^Підсумок написано не англійською$'):
        validate_summary(GOOD, 1200, 'en')


def test_block_timeline_skips_sources_from_a_trashed_scene(tmp_path):
    # Cross-review #1: a cumulative journal still names the prose of a scene moved to the trash; the block timeline
    # leaves that entry out instead of failing on the trashed scene.
    from storygen.generation.timeline_summary import _timeline
    from storygen.memory.summary_blocks import summary_blocks
    repo, story = long_story(tmp_path, 22, 21)
    scenes = repo.list_scenes(story.id)
    memory_id = scenes[11].heads['memory']  # scene 12 remembers scenes 1-12
    repo.set_scene_trashed(story.id, scenes[2].id, repo.get_scene(scenes[2].id).revision, False)
    view = repo.context_view(story.id)
    active = view.list_scenes(story.id)
    block = summary_blocks(view.get_story(story.id), active)[0]
    lines = _timeline(view, active, block, memory_id, 'uk')
    assert len(lines) == 10 and not any('вулицю номер 3' in line for line in lines)
