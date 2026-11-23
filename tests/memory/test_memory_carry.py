"""Mechanical memory carry: a new memory of a scene is carried into the journals of later scenes (neutral texts)."""
import json

import pytest

from storygen.domain import RevisionConflict
from storygen.generation.dependencies import save_manual_draft, save_manual_prose
from storygen.generation.readiness import preview
from storygen.memory.carry import CarryFailed, carry_journal, carry_state
from storygen.memory.journal import MemoryJournal, _add_event, _change_event, load_memory
from storygen.memory.previous import previous_memory, read_previous_journal
from storygen.memory.service import save_scene_memory
from storygen.run_models import RunRequest
from storygen.storage.link_decisions import decide_link
from storygen.storage.links import link_state, memory_digest, own_events
from tests.storage.test_links import book, memory_text, statuses

QUOTE = 'Олена увійшла'
CARRYING = 'Пам’ять переноситься'


def carry_runs(repo, story_id):
    return [run for run in repo.list_runs(story_id) if run.request.mode == 'memory_carry']


def run_carries(repo, story_id):
    """Execute the queued carry runs in queue order, as the worker would."""
    from storygen.generation.worker import RunCoordinator
    worker = RunCoordinator(repo)
    for run in carry_runs(repo, story_id):
        current = repo.get_run(run.id)
        if current.state != 'queued':
            continue
        current.state = 'running'
        repo.save_run(current)
        worker._execute(run.id)
    return [repo.get_run(run.id) for run in carry_runs(repo, story_id)]


def journal_of(repo, scene):
    return load_memory(memory_text(repo, scene))


def state(repo, story, scene):
    return carry_state(repo.context_view(story.id), scene.id)


def new_memory(repo, scene, text='Олена в бібліотеці вночі'):
    """The author rewrites the scene's last own record: a new memory head with other own events."""
    journal = json.loads(memory_text(repo, scene))
    journal['events'][-1]['text'] = text
    save_scene_memory(repo, scene.id, json.dumps(journal, ensure_ascii=False), repo.get_scene(scene.id).revision)


def memory_on_previous(repo, scene, keep=lambda event: True, extra=()):
    """A manual memory of the scene built on the current journal of its previous memory."""
    scene = repo.get_scene(scene.id)
    view = repo.context_view(scene.story_id)
    previous = read_previous_journal(view, previous_memory(view, scene))
    own = [event for event in own_events(journal_of(repo, scene)) if keep(event)] + list(extra)
    journal = MemoryJournal(schema_version=3, source_prose_ids=previous.source_prose_ids + [scene.heads['prose']],
                            events=previous.events + own)
    save_scene_memory(repo, scene.id, journal.model_dump_json(), scene.revision)


def failed_book(tmp_path, count=3):
    """Scene 2 resolves an open thread of scene 1; the author then renames that thread in a new memory of scene 1."""
    repo, story, scenes = book(tmp_path, count)
    first = repo.get_scene(scenes[0].id)
    thread = _add_event('open_threads', 'Хто залишив книжку?', first.heads['prose'], QUOTE, 0)
    journal = journal_of(repo, first)
    save_scene_memory(repo, first.id, journal.model_copy(update={'events': journal.events + [thread]}).model_dump_json(),
                      first.revision)
    second = repo.get_scene(scenes[1].id)
    update = _change_event('update', thread.claim_id, 'Книжку залишила Олена', 'open_threads', [], second.heads['prose'], QUOTE)
    memory_on_previous(repo, second, extra=[update])
    run_carries(repo, story.id)
    assert all(state(repo, story, s) == 'current' for s in scenes[1:])
    journal = json.loads(memory_text(repo, first))
    journal['events'][-1]['text'] = 'Хто приніс книжку?'
    save_scene_memory(repo, first.id, json.dumps(journal, ensure_ascii=False), repo.get_scene(first.id).revision)
    return repo, story, scenes


@pytest.mark.req('VALID-MEMORY')
def test_carry_journal_extends_the_new_previous_journal_with_own_events():
    previous = MemoryJournal(source_prose_ids=['p1'], events=[_add_event('facts', 'Нове', 'p1', 'Олена', 0)])
    old = _add_event('facts', 'Старе', 'p1', 'Олена', 0)
    own = _add_event('facts', 'Своє', 'p2', 'Олена', 0)
    carried = carry_journal(previous, MemoryJournal(source_prose_ids=['p1', 'p2'], events=[old, own]))
    assert carried.source_prose_ids == ['p1', 'p2'] and carried.events == previous.events + [own]
    update = _change_event('update', old.claim_id, 'Змінене', 'open_threads', [], 'p2', 'Олена')
    with pytest.raises(CarryFailed):
        carry_journal(previous, MemoryJournal(source_prose_ids=['p1', 'p2'], events=[old.model_copy(update={'category': 'open_threads'}),
                                                                                    update]))


@pytest.mark.req('VALID-MEMORY')
def test_carry_keeps_own_events_and_digest(tmp_path):
    repo, story, scenes = book(tmp_path, 3)
    second, third = scenes[1], scenes[2]
    own_before = own_events(journal_of(repo, second))
    digest = memory_digest(repo.context_view(story.id), repo.get_scene(second.id).heads['memory'])
    new_memory(repo, scenes[0])
    assert state(repo, story, second) == 'pending'
    assert statuses(repo, story, second)['memory'] == ('unavailable', None, 'carry_pending')
    runs = run_carries(repo, story.id)
    assert [run.state for run in runs] == ['completed']
    first, carried = journal_of(repo, scenes[0]), journal_of(repo, second)
    assert carried.source_prose_ids == first.source_prose_ids + [repo.get_scene(second.id).heads['prose']]
    assert carried.events == first.events + own_before
    view = repo.context_view(story.id)
    assert memory_digest(view, repo.get_scene(second.id).heads['memory']) == digest
    # The pending state clears once the run has finished.
    assert carry_state(view, second.id) == 'current' and carry_state(view, third.id) == 'current'
    assert statuses(repo, story, second)['memory'] == ('valid', 'construction', None)
    after = statuses(repo, story, third)
    assert after['brief'] == ('valid', 'construction', None) and after['prose'] == ('valid', 'construction', None)


@pytest.mark.req('VALID-MEMORY')
def test_carry_fails_on_missing_claim(tmp_path):
    repo, story, scenes = failed_book(tmp_path)
    second, third = (repo.get_scene(s.id) for s in scenes[1:])
    runs = run_carries(repo, story.id)
    assert runs[-1].state == 'completed' and runs[-1].checkpoint['failed_scene_id'] == second.id
    assert repo.get_scene(second.id).heads['memory'] == second.heads['memory']
    assert repo.get_scene(third.id).heads['memory'] == third.heads['memory']
    assert state(repo, story, second) == 'failed'
    current = link_state(repo.context_view(story.id), second.id, 'memory')
    assert (current.status, current.reason) == ('unavailable', 'carry_failed')
    with pytest.raises(RevisionConflict):
        decide_link(repo, second.id, 'memory', 'approve', current.fingerprint)


@pytest.mark.req('VALID-MEMORY')
def test_new_memory_clears_carry_failed_and_continues(tmp_path):
    repo, story, scenes = failed_book(tmp_path)
    run_carries(repo, story.id)
    memory_on_previous(repo, scenes[1], keep=lambda event: event.operation == 'add')
    assert state(repo, story, scenes[1]) == 'current'
    assert state(repo, story, scenes[2]) == 'pending'
    assert run_carries(repo, story.id)[-1].state == 'completed'
    second, third = journal_of(repo, scenes[1]), journal_of(repo, scenes[2])
    assert third.source_prose_ids[:-1] == second.source_prose_ids and third.events[:len(second.events)] == second.events
    assert state(repo, story, scenes[2]) == 'current'


@pytest.mark.req('VALID-MEMORY')
def test_model_stages_refused_while_carrying(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    repo, story, scenes = book(tmp_path, 3)
    new_memory(repo, scenes[0])
    for scene in scenes[1:]:
        result = preview(repo, RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='draft'))
        assert not result['ready'] and CARRYING in result['reason']
    assert CARRYING not in (preview(repo, RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='stage', stage='draft'))['reason'] or '')
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='remaining'))
    assert CARRYING in result['reason']
    third = repo.get_scene(scenes[2].id)
    save_manual_prose(repo, third.id, 'Олена увійшла до нової бібліотеки вночі.', third.revision)
    third = repo.get_scene(third.id)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')
    response = client.post(f'/api/scenes/{third.id}/draft', json={
        'text': 'Чат пише.', 'expected_revision': third.revision, 'content_format': 'markdown',
        # The writing context itself cannot be built while the memory it extends is carried: any read fingerprint.
        'expected_context_fingerprint': '0' * 64, 'external_origin': {'client': 'Claude', 'model': 'm'},
        'expected_draft_version_id': third.heads.get('draft')})
    assert response.status_code == 409 and CARRYING in response.json()['detail']


@pytest.mark.req('VALID-MEMORY')
def test_carry_restarts_from_an_earlier_change(tmp_path):
    repo, story, scenes = book(tmp_path, 4)
    new_memory(repo, scenes[1])
    new_memory(repo, scenes[0])
    first, second = carry_runs(repo, story.id)
    assert first.tasks[0]['scene_id'] == scenes[2].id and second.tasks[0]['scene_id'] == scenes[1].id
    run_carries(repo, story.id)
    assert repo.get_run(first.id).state == 'cancelled'
    assert any(event.type == 'superseded' for event in repo.list_run_events(first.id))
    assert repo.get_run(second.id).state == 'completed'
    for previous, scene in zip(scenes, scenes[1:]):
        before, after = journal_of(repo, previous), journal_of(repo, scene)
        assert after.events[:len(before.events)] == before.events
        assert state(repo, story, scene) == 'current'


@pytest.mark.req('VALID-MEMORY')
def test_carry_step_respects_scene_revision(tmp_path, monkeypatch):
    from storygen.storage.repository import Repository
    repo, story, scenes = book(tmp_path, 2)
    new_memory(repo, scenes[0])
    original = Repository.commit_memory_carry
    calls = []

    def racing(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            # The author saves a draft of the scene between the carry's read and its commit.
            save_manual_draft(repo, scenes[1].id, 'Авторська чернетка.', repo.get_scene(scenes[1].id).revision)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Repository, 'commit_memory_carry', racing)
    assert run_carries(repo, story.id)[-1].state == 'completed'
    assert len(calls) == 2
    assert repo.read_text(repo.get_scene(scenes[1].id).heads['draft']) == 'Авторська чернетка.'
    assert state(repo, story, scenes[1]) == 'current'


@pytest.mark.req('VALID-MEMORY')
def test_carry_skips_scene_without_memory(tmp_path):
    repo, story, scenes = book(tmp_path, 3)
    second = repo.get_scene(scenes[1].id)
    with repo.db.connection() as db:
        payload = second.model_copy(update={'heads': {k: v for k, v in second.heads.items() if k != 'memory'}})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), second.id))
    third_memory = repo.get_scene(scenes[2].id).heads['memory']
    new_memory(repo, scenes[0])
    memories = len(repo.list_versions(story.id, second.id, 'memory'))
    assert run_carries(repo, story.id)[-1].state == 'completed'
    assert 'memory' not in repo.get_scene(second.id).heads
    assert len(repo.list_versions(story.id, second.id, 'memory')) == memories
    assert repo.get_scene(scenes[2].id).heads['memory'] == third_memory


@pytest.mark.req('VALID-MEMORY')
def test_carry_through_merge_and_series_start(tmp_path):
    from storygen.memory.series_start import read_series_start
    from storygen.storage import series as store
    from storygen.storage.memory_merges import merge_point, save_merge
    from storygen.storage.repository import Repository
    from tests.memory.merge_helpers import arc_book, save_scene_journal
    from tests.series.helpers import into_series
    # A series book of one arc: scene 2 extends scene 1, which extends the start snapshot.
    repo = Repository(tmp_path / 'series')
    item = store.create_series(repo, 'Серія')
    _, first, _ = arc_book(tmp_path, 'A', [['A']], repo=repo)
    into_series(repo, first, item.id, 1)
    _, story, scenes = arc_book(tmp_path, 'A A', [['A']], repo=repo, only={99})
    story = into_series(repo, story, item.id, 2)
    start = read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id).journal
    from tests.memory.merge_helpers import fact
    previous = start
    for scene in scenes:
        scene = repo.get_scene(scene.id)
        save_scene_journal(repo, scene, previous, [fact(f'Подія {scene.title}', scene.heads['prose'])])
        previous = journal_of(repo, scene)
    new_memory(repo, scenes[0], 'Анна йде містом уночі')
    assert run_carries(repo, story.id)[-1].state == 'completed'
    carried = journal_of(repo, scenes[1])
    assert carried.source_prose_ids[0] == story.series_start_version_id
    assert carried.events[:len(journal_of(repo, scenes[0]).events)] == journal_of(repo, scenes[0]).events
    assert state(repo, story, scenes[1]) == 'current'
    # Arcs A and B meet in scene 3: a new memory of scene 1 makes the merge unusable, and the carry stops before scene 3.
    repo, story, scenes = arc_book(tmp_path / 'merge', 'A B A+B', [['A', 'B']])
    point = merge_point(story, repo.list_scenes(story.id), scene_id=scenes[2].id)
    story, version_id = save_merge(repo, story.id, point.key, {}, story.revision, [scenes[0].heads['memory'], scenes[1].heads['memory']])
    merged = MemoryJournal.model_validate(json.loads(repo.read_text(version_id))['journal'])
    third = repo.get_scene(scenes[2].id)
    save_scene_journal(repo, third, merged, [fact('Зустріч', third.heads['prose'])])
    third_memory = repo.get_scene(third.id).heads['memory']
    new_memory(repo, scenes[0], 'Анна йде містом уночі')
    run = run_carries(repo, story.id)[-1]
    assert run.state == 'completed' and run.checkpoint['stopped_scene_id'] == third.id
    assert run.checkpoint['reason'] == 'merge_required' and 'злиття' in run.warning
    assert repo.get_scene(third.id).heads['memory'] == third_memory
    assert state(repo, story, scenes[1]) in {'current', None}
    assert state(repo, story, third) != 'failed'


@pytest.mark.req('VALID-MEMORY')
def test_carry_does_not_launder_memory_links(tmp_path):
    from tests.link_helpers import approve_links
    repo, story, scenes = book(tmp_path / 'clean', 3)
    new_memory(repo, scenes[0])
    # The new memory of scene 1 unchecks Z1/Z2 of scene 2 (and so its prose, an input of scene 3); the author keeps them.
    approve_links(repo, story.id, {scenes[1].id})
    run_carries(repo, story.id)
    view = repo.context_view(story.id)
    third = view.scenes[scenes[2].id]
    assert not view.is_stale(third.heads['draft'])
    assert statuses(repo, story, scenes[2]) == {link: ('valid', 'construction', None) for link in ('brief', 'prose', 'memory')}


def keep_memory(repo, story, scene):
    link = link_state(repo.context_view(story.id), scene.id, 'memory')
    decide_link(repo, scene.id, 'memory', 'approve', link.fingerprint)


@pytest.mark.req('VALID-MEMORY')
@pytest.mark.parametrize('decide, expected', [
    (lambda repo, story, scene: None, ('unchecked', None, None)),
    (keep_memory, ('valid', 'author', None)),
], ids=['unchecked', 'kept'])
def test_carry_keeps_the_memory_link_of_a_hand_edited_scene(tmp_path, decide, expected):
    # An unchecked Z3 stays unchecked; a Z3 the author kept stays valid.
    repo, story, scenes = book(tmp_path, 3)
    second = repo.get_scene(scenes[1].id)
    save_manual_prose(repo, second.id, 'Олена увійшла до нової бібліотеки вночі.', second.revision)
    decide(repo, story, second)
    assert statuses(repo, story, second)['memory'] == expected
    new_memory(repo, scenes[0])
    run_carries(repo, story.id)
    assert state(repo, story, second) == 'current'
    assert statuses(repo, story, second)['memory'] == expected


@pytest.mark.req('VALID-MEMORY')
def test_carry_step_enqueues_no_carry(tmp_path):
    repo, story, scenes = book(tmp_path, 3)
    heads = [repo.get_scene(s.id).heads['memory'] for s in scenes[1:]]
    new_memory(repo, scenes[0])
    assert len(carry_runs(repo, story.id)) == 1
    run_carries(repo, story.id)
    assert [repo.get_scene(s.id).heads['memory'] for s in scenes[1:]] != heads
    assert len(carry_runs(repo, story.id)) == 1


@pytest.mark.req('VALID-MEMORY')
def test_carry_reasons_name_the_scene_and_action(tmp_path):
    from storygen.generation.context import build_context
    from storygen.providers.models import ProviderSettings, RoleSettings
    repo, story, scenes = failed_book(tmp_path)
    settings = RoleSettings(provider=ProviderSettings(model='writer'))
    with pytest.raises(ValueError, match='переноситься'):
        build_context(repo, scenes[2].id, 'brief', settings)
    run_carries(repo, story.id)
    with pytest.raises(ValueError, match='створіть нову пам’ять цієї сцени') as error:
        build_context(repo, scenes[2].id, 'brief', settings)
    assert repo.get_scene(scenes[1].id).title in str(error.value)


@pytest.mark.req('VALID-MEMORY')
def test_selecting_a_memory_again_carries_again(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    old = repo.get_scene(scenes[0].id).heads['memory']
    new_memory(repo, scenes[0])
    new = repo.get_scene(scenes[0].id).heads['memory']
    run_carries(repo, story.id)
    for head in (old, new):
        repo.set_head(scenes[0].id, 'memory', head, repo.get_scene(scenes[0].id).revision)
        assert state(repo, story, scenes[1]) == 'pending'
        run_carries(repo, story.id)
        assert state(repo, story, scenes[1]) == 'current'
    assert len(carry_runs(repo, story.id)) == 3


@pytest.mark.req('VALID-MEMORY')
def test_stalled_carry_keeps_its_scenes_pending(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    new_memory(repo, scenes[0])
    (run,) = carry_runs(repo, story.id)
    for stalled in ('paused', 'failed', 'interrupted'):
        run.state = stalled
        repo.save_run(run)
        assert state(repo, story, scenes[1]) == 'pending'
    # Resumed, it carries the scene.
    run.state = 'queued'
    repo.save_run(run)
    run_carries(repo, story.id)
    assert state(repo, story, scenes[1]) == 'current'


@pytest.mark.req('VALID-MEMORY')
def test_chat_stage_result_refused_while_carrying(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    repo, story, scenes = book(tmp_path, 2)
    new_memory(repo, scenes[0])
    client = TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')
    response = client.post(f'/api/scenes/{scenes[1].id}/chat-result/memory', json={
        'task_fingerprint': '0' * 64, 'text': '{}', 'external_origin': {'client': 'Claude', 'model': 'm'}})
    assert response.status_code == 409 and CARRYING in response.json()['detail']


@pytest.mark.req('VALID-MEMORY')
def test_stop_warning_names_the_real_reason():
    from storygen.generation.memory_carry import FAILED, stop_warning
    from storygen.memory.carry import CARRY_MISSING
    assert stop_warning('Ранок', CARRY_MISSING) == FAILED.replace('{p0}', 'Ранок')
    assert stop_warning('Ранок', None) == FAILED.replace('{p0}', 'Ранок')
    # Not author text (a KeyError or a pydantic message): the general sentence.
    assert stop_warning('Ранок', "'claim-1'") == FAILED.replace('{p0}', 'Ранок')
    assert stop_warning('Ранок', '1 validation error for MemoryJournal') == FAILED.replace('{p0}', 'Ранок')
    text = stop_warning('Ранок', 'Пам’ять сцени не має власного джерела.\nДругий рядок')
    assert text == 'Перенос пам’яті зупинено на сцені «Ранок»: Пам’ять сцени не має власного джерела. Другий рядок — створіть нову пам’ять цієї сцени'
    assert '\n' not in text


@pytest.mark.req('VALID-MEMORY')
def test_stalled_carry_can_be_resumed_or_cancelled(tmp_path):
    from storygen.generation.worker import RunCoordinator
    from storygen.storage.material_status import material_status
    repo, story, scenes = book(tmp_path, 3)
    new_memory(repo, scenes[0])
    (run,) = carry_runs(repo, story.id)
    worker = RunCoordinator(repo)
    for stalled in ('paused', 'failed', 'interrupted'):
        run.state = stalled
        repo.save_run(run)
        row = material_status(repo.context_view(story.id))[scenes[1].id]
        assert row['links']['memory']['reason'] == 'carry_pending'
        assert row['carry_run'] == {'id': run.id, 'state': stalled}
    # A failed carry (three conflicts in a row, a scene trashed mid-step) can be cancelled: its scenes stop waiting.
    assert worker.cancel(run.id).state == 'cancelled'
    assert state(repo, story, scenes[1]) != 'pending'
    assert 'carry_run' not in material_status(repo.context_view(story.id))[scenes[1].id]
    # A paused carry resumes without a paid call and carries the scenes.
    repo2, story2, scenes2 = book(tmp_path / 'resume', 3)
    new_memory(repo2, scenes2[0])
    (paused,) = carry_runs(repo2, story2.id)
    paused.state = 'paused'
    repo2.save_run(paused)
    assert RunCoordinator(repo2).resume(paused.id, True).state == 'queued'
    run_carries(repo2, story2.id)
    assert all(state(repo2, story2, s) == 'current' for s in scenes2[1:])


@pytest.mark.req('VALID-MEMORY')
def test_carried_memory_keeps_the_source_run_of_its_memory(tmp_path):
    # A carried copy is not a new model result: an author-written memory stays author-written (STORY-LANGUAGE lock).
    repo, story, scenes = book(tmp_path, 3)
    old = repo.get_scene(scenes[1].id).heads['memory']
    new_memory(repo, scenes[0])
    run_carries(repo, story.id)
    carried = repo.get_scene(scenes[1].id).heads['memory']
    view = repo.context_view(story.id)
    assert carried != old and view.versions[carried].memory_carry_of == old
    assert view.versions[carried].source_run_id == view.versions[old].source_run_id


@pytest.mark.req('VALID-MEMORY')
def test_confirming_a_merge_carries_the_scenes_after_it(tmp_path):
    from storygen.storage.memory_merges import merge_point, save_merge
    from tests.memory.merge_helpers import arc_book, fact, save_scene_journal
    repo, story, scenes = arc_book(tmp_path, 'A B A+B A+B', [['A', 'B']], only={1, 2})
    point = merge_point(story, repo.list_scenes(story.id), scene_id=scenes[2].id)
    heads = lambda: [repo.get_scene(s.id).heads['memory'] for s in scenes[:2]]
    story, version_id = save_merge(repo, story.id, point.key, {}, story.revision, heads())
    previous = MemoryJournal.model_validate(json.loads(repo.read_text(version_id))['journal'])
    for scene in scenes[2:]:
        scene = repo.get_scene(scene.id)
        save_scene_journal(repo, scene, previous, [fact(f'Подія {scene.title}', scene.heads['prose'])])
        previous = journal_of(repo, scene)
    run_carries(repo, story.id)
    new_memory(repo, scenes[0], 'Анна йде містом уночі')
    assert run_carries(repo, story.id)[-1].checkpoint['stopped_scene_id'] == scenes[2].id
    third = repo.get_scene(scenes[2].id).heads['memory']
    # The author confirms the merge, as the stop warning asks: the scenes after the merge point are carried.
    story = repo.get_story(story.id)
    story, version_id = save_merge(repo, story.id, point.key, {}, story.revision, heads())
    assert run_carries(repo, story.id)[-1].state == 'completed'
    assert repo.get_scene(scenes[2].id).heads['memory'] != third
    merged = MemoryJournal.model_validate(json.loads(repo.read_text(version_id))['journal'])
    assert journal_of(repo, scenes[2]).events[:len(merged.events)] == merged.events
    assert all(state(repo, story, s) == 'current' for s in scenes[2:])


@pytest.mark.req('VALID-MEMORY')
def test_scenes_after_a_failed_carry_wait_for_it(tmp_path):
    from storygen.memory.carry import carry_blocker, carry_blocks
    from storygen.storage.material_status import material_status
    repo, story, scenes = failed_book(tmp_path, 4)
    run_carries(repo, story.id)
    view = repo.context_view(story.id)
    assert state(repo, story, scenes[1]) == 'failed'
    # Scenes 3 and 4 still inherit the old memory of scene 1: their model stages wait, naming the failed scene.
    for scene in scenes[2:]:
        assert carry_state(view, scene.id) == 'pending' and carry_blocks(view, scene.id)
        assert carry_blocker(view, scene.id) == scenes[1].id
        assert material_status(view)[scene.id]['carry_failed_scene_id'] == scenes[1].id
        assert 'carry_run' not in material_status(view)[scene.id]
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='memory'), view)
    assert not result['ready'] and scenes[1].title in result['reason'] and 'перебудуєте' in result['reason']
    # A new memory of scene 2 lifts the stop, and the carry reaches scenes 3 and 4.
    memory_on_previous(repo, scenes[1], keep=lambda event: event.operation == 'add')
    run_carries(repo, story.id)
    assert all(state(repo, story, s) == 'current' for s in scenes[1:])
