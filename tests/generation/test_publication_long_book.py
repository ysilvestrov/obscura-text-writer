"""R16-SUGGEST-S07/S08: a long book gets the idea and the longest prefix of whole scenes; the selection is visible."""
import json

import pytest

from storygen.authoring.blueprints import get_role_settings, save_role_settings
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import RevisionConflict, StoryCreate
from storygen.generation.context import ContextOverflow
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.publication_metadata import (SELECTION_CHANGED, build_publication_context, largest_prefix,
                                                      readiness, suggestions_state)
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.publication_models import PublicationData
from storygen.run_models import RunRequest
from storygen.storage.plan_preamble import replace_plan_preamble
from storygen.storage.repository import Repository

IDEA = 'Задум: доглядачка маяка шукає зниклого брата.'
SCENE_PROSE = 'Хвилі билися об каміння, і ліхтар світив крізь туман. ' * 20


def plan(scenes, idea=IDEA):
    head = f'{idea}\n\n' if idea else ''
    return head + ''.join(f'## Сцена {i + 1}: Частина {i + 1}\nОпис {i + 1}\n' for i in range(scenes))


def writer(repo, story_id, **values):
    role = RoleSettings(provider=ProviderSettings(model='writer-test', response_mode='json_schema'),
                        **{'context_tokens': 1_000_000, 'max_input_chars': 10_000_000, 'max_output_tokens': 2048, **values})
    save_role_settings(repo, story_id, 'writer', role, repo.get_story(story_id).revision)


def book(root, scenes=6, idea=IDEA):
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Маяк'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=plan(scenes, idea).encode())])
    for scene in repo.list_scenes(story.id):
        save_manual_prose(repo, scene.id, f'{scene.title}. {SCENE_PROSE}', repo.get_scene(scene.id).revision)
    writer(repo, story.id)
    return repo, repo.get_story(story.id)


def chars(context):
    return len(json.dumps(context.api_request, ensure_ascii=False, separators=(',', ':')))


def user(context):
    return json.loads(context.user_text)


def selection(context):
    return json.loads(context.fragments['publication_selection'])


def limited(repo, story, scenes_short):
    """A character limit that lets every scene in except the last `scenes_short`, by the measured per-scene size."""
    full = build_publication_context(repo, story.id)
    per_scene = len(json.dumps(user(full)['scenes'][-1], ensure_ascii=False)) + 1  # scene object and its comma
    writer(repo, story.id, max_input_chars=chars(full) - per_scene * scenes_short + per_scene // 2)
    return selection(full)['total']


class Gateway:
    def __init__(self):
        self.requests = []

    def stream(self, *args):
        self.requests.append(args)
        payload = {'title': None, 'annotation': 'Анотація.', 'genres': ['short_story'], 'keywords': ['маяк']}
        yield GenerationEvent(type='delta', text=json.dumps(payload, ensure_ascii=False))
        yield GenerationEvent(type='terminal', finish_reason='stop', usage={'prompt_tokens': 10, 'completion_tokens': 5})


def execute(repo, request, request_id='long-book'):
    gateway = Gateway()
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    run = worker.enqueue(request, request_id)
    run.state = 'running'
    repo.save_run(run)
    worker._execute(run.id)
    return gateway, repo.get_run(run.id)


@pytest.mark.req('R16-SUGGEST')
def test_whole_book_gets_the_idea_and_full_coverage(tmp_path):
    repo, story = book(tmp_path, 3)
    context = build_publication_context(repo, story.id)
    data = user(context)
    assert data['idea'] == IDEA and data['coverage'] == {'scenes_included': 3, 'scenes_total': 3}
    assert len(data['scenes']) == 3 and 'Опис 1' not in context.user_text  # scene plans stay out
    assert selection(context)['included'] == 3 and selection(context)['bound_by'] is None
    assert context.system_text.startswith('Ти готуєш') and 'coverage' in context.system_text
    assert repo.active_source(story.id, 'source_plan').id in context.input_refs
    ready = readiness(repo, RunRequest(story_id=story.id, mode='publication_suggest'), enforce_selection=False)
    assert ready['ready'] and ready['warnings'] == [] and ready['selection']['included'] == 3


@pytest.mark.req('R16-SUGGEST')
def test_long_book_reads_the_idea_and_the_longest_prefix_of_whole_scenes(tmp_path):
    repo, story = book(tmp_path, 6)
    total = limited(repo, story, 2)
    context = build_publication_context(repo, story.id)
    data, picked = user(context), selection(context)
    assert picked['included'] == total - 2 and picked['total'] == total and picked['idea'] is True
    assert picked['bound_by'] == 'chars' and picked['last_scene_title'] == f'Частина {total - 2}'
    assert [s['title'] for s in data['scenes']] == [f'Частина {i + 1}' for i in range(total - 2)]
    assert all(s['text'].endswith(SCENE_PROSE) for s in data['scenes'])  # whole scenes, never cut
    assert data['coverage'] == {'scenes_included': total - 2, 'scenes_total': total}
    assert chars(context) <= get_role_settings(repo, story.id)['writer'].max_input_chars
    assert len(context.input_refs) == total - 2 + 1
    ready = readiness(repo, RunRequest(story_id=story.id, mode='publication_suggest'), enforce_selection=False)
    assert ready['ready'] and ready['selection'] == picked
    assert ready['warnings'] == [f'Книжка не вміщається у вікно моделі повністю: модель прочитає ідею твору й сцени '
                                 f'1–{total - 2} із {total} (до «Частина {total - 2}»). Межа — ліміт символів письменника; '
                                 f'його можна підняти в налаштуваннях моделей.']


@pytest.mark.req('R16-SUGGEST')
def test_long_book_without_an_idea_says_so(tmp_path):
    repo, story = book(tmp_path, 5, idea='')
    total = limited(repo, story, 1)
    context = build_publication_context(repo, story.id)
    assert 'idea' not in user(context) and selection(context)['idea'] is False
    ready = readiness(repo, RunRequest(story_id=story.id, mode='publication_suggest'), enforce_selection=False)
    assert ready['warnings'][0].startswith(f'Книжка не вміщається у вікно моделі повністю: модель прочитає сцени 1–{total - 1} із {total}')
    assert ', без ідеї твору.' in ready['warnings'][0]


@pytest.mark.req('R16-SUGGEST')
def test_a_preamble_with_only_a_title_heading_is_no_idea(tmp_path):
    repo, story = book(tmp_path, 3, idea='# Маяк')
    context = build_publication_context(repo, story.id)
    assert 'idea' not in user(context) and selection(context)['idea'] is False
    assert 'idea_sha256' not in json.loads(context.fragments['publication_sources'])
    repo2, story2 = book(tmp_path / 'titled', 3, idea=f'# Маяк\n\n{IDEA}')
    assert user(build_publication_context(repo2, story2.id))['idea'] == f'# Маяк\n\n{IDEA}'


@pytest.mark.req('R16-SUGGEST')
def test_even_the_idea_and_the_first_scene_do_not_fit(tmp_path):
    repo, story = book(tmp_path, 3)
    writer(repo, story.id, max_input_chars=200)
    with pytest.raises(ContextOverflow, match='Текст не обрізано'):
        build_publication_context(repo, story.id)
    called = []
    worker = RunCoordinator(repo, gateway_factory=lambda p: called.append(p))
    with pytest.raises(ValueError):
        worker.enqueue(RunRequest(story_id=story.id, mode='publication_suggest'), 'none-fits')
    assert not called and not repo.list_runs(story.id)


def test_prefix_search_survives_a_token_estimate_that_jumps():
    """Cross-review #1: the profile estimate is cheap inside its byte range and conservative outside it."""
    chars_fit = lambda k: k <= 9
    tokens_fit = lambda k: k >= 4 and k <= 7  # a short request falls outside the profile range and "does not fit"
    assert largest_prefix(12, chars_fit, tokens_fit) == 7
    assert largest_prefix(12, lambda k: True, lambda k: False) == 0
    assert largest_prefix(5, lambda k: k <= 2, lambda k: True) == 2


@pytest.mark.req('R16-SUGGEST')
def test_incomplete_reading_runs_only_with_the_selection_the_author_saw(tmp_path):
    repo, story = book(tmp_path, 6)
    total = limited(repo, story, 2)
    called = []
    worker = RunCoordinator(repo, gateway_factory=lambda p: called.append(p))
    with pytest.raises(ValueError, match=SELECTION_CHANGED):
        worker.enqueue(RunRequest(story_id=story.id, mode='publication_suggest'), 'no-key')
    with pytest.raises(ValueError, match=SELECTION_CHANGED):
        worker.enqueue(RunRequest(story_id=story.id, mode='publication_suggest', expected_selection='0' * 64), 'old-key')
    assert not called and not repo.list_runs(story.id)
    key = readiness(repo, RunRequest(story_id=story.id, mode='publication_suggest'), enforce_selection=False)['selection']['key']
    gateway, run = execute(repo, RunRequest(story_id=story.id, mode='publication_suggest', expected_selection=key))
    assert run.state == 'completed' and len(gateway.requests) == 1
    attempt = repo.list_attempts(story.id, run.id)[0]
    assert attempt.context['publication_selection']['included'] == total - 2
    assert len(json.loads(attempt.context['user_text'])['scenes']) == total - 2
    state = suggestions_state(repo, story.id)
    assert state['proposals'][0]['selection']['included'] == total - 2 and state['proposals'][0]['can_apply']
    assert state['history'][0]['selection']['included'] == total - 2


@pytest.mark.req('R16-SUGGEST')
def test_selection_changed_after_the_preview_is_refused_before_dispatch(tmp_path):
    repo, story = book(tmp_path, 6)
    total = limited(repo, story, 1)
    key = readiness(repo, RunRequest(story_id=story.id, mode='publication_suggest'), enforce_selection=False)['selection']['key']
    gateway = Gateway()
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, mode='publication_suggest', expected_selection=key), 'changed')
    current = get_role_settings(repo, story.id)['writer']
    writer(repo, story.id, max_input_chars=current.max_input_chars - 2000)  # the writer limit is lowered meanwhile
    run.state = 'running'
    repo.save_run(run)
    with pytest.raises(ValueError, match=SELECTION_CHANGED):  # the worker loop records it as the run's failure
        worker._execute(run.id)
    assert not gateway.requests and not repo.list_attempts(story.id, run.id)
    assert worker._failure_message(repo.get_run(run.id), ValueError(SELECTION_CHANGED)) == SELECTION_CHANGED
    assert total == 6


def test_full_book_runs_without_a_selection_key(tmp_path):
    repo, story = book(tmp_path, 2)
    gateway, run = execute(repo, RunRequest(story_id=story.id, mode='publication_suggest'))
    assert run.state == 'completed' and len(gateway.requests) == 1


def test_selection_key_only_for_the_publication_suggestion():
    with pytest.raises(ValueError, match='Відбір сцен'):
        RunRequest(story_id='s', scene_id='x', mode='scene', expected_selection='0' * 64)


@pytest.mark.req('R16-SUGGEST')
def test_changed_idea_makes_the_proposal_stale_and_no_idea_keeps_the_old_stamp(tmp_path):
    repo, story = book(tmp_path, 2)
    gateway, run = execute(repo, RunRequest(story_id=story.id, mode='publication_suggest'))
    proposal = suggestions_state(repo, story.id)['proposals'][0]
    stamp = repo.list_attempts(story.id, run.id)[0].context['publication_proposal']['source_stamp']
    assert 'idea_sha256' in stamp
    plan_id = repo.active_source(story.id, 'source_plan').id
    replace_plan_preamble(repo, story.id, plan_id, 'Задум: інший.')
    assert not suggestions_state(repo, story.id)['proposals'][0]['can_apply']
    data = PublicationData(annotation=proposal['suggestions']['annotation'], genres=['short_story'], keywords=['маяк'])
    with pytest.raises(RevisionConflict):
        repo.publication('save_card', story_id=story.id, data=data, expected_revision=0, expected_signature_revisions={},
                         suggestion={'attempt_id': proposal['attempt_id'], 'fingerprint': proposal['fingerprint'],
                                     'fields': ['annotation', 'genres', 'keywords']})
    repo2, story2 = book(tmp_path / 'plain', 2, idea='')
    snapshot = repo2.publication_snapshot(story2.id)
    from storygen.publication_suggestions import source_stamp
    assert set(source_stamp(snapshot)) == {'story_id', 'title', 'scenes'}
