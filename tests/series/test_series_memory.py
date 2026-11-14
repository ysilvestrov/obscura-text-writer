"""SERIES-S03: the start snapshot is scene 0 of a series book's memory (neutral examples)."""
import threading

from storygen.domain import SceneCreate
from storygen.generation.context import build_context, memory_projection
from storygen.generation.models import WritersBrief
from storygen.generation.stages import execute_stage
from storygen.memory.journal import load_memory
from storygen.memory.projection import MemoryItem
from storygen.memory.reuse import memory_for_manual_edit
from storygen.memory.selection import TIMELINE_WINDOW, SelectionInput, select_memory
from storygen.providers.streaming import GenerationEvent
from storygen.storage import series as store
from storygen.storage.repository import Repository
from tests.memory.test_core_review import role, run_memory
from tests.memory.wire_helpers import v4_answer
from tests.series.helpers import book, finished_book, into_series, prose


class BriefGateway:
    def stream(self, *_):
        yield GenerationEvent(type='delta', text=WritersBrief(objective='o', beats=['b']).model_dump_json())
        yield GenerationEvent(type='terminal', finish_reason='stop')


def second_book(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, _, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second, scene = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    assert second.series_start_version_id
    return repo, item, second, repo.get_scene(scene.id), cloth


def write_scene_memory(repo, scene):
    context = build_context(repo, scene.id, 'memory', role())
    return run_memory(repo, scene, v4_answer(context)).result_version_id


def write_brief(repo, scene):
    context = build_context(repo, scene.id, 'brief', role())
    attempt = execute_stage(repo, scene.id, 'brief', context, BriefGateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed', attempt.error
    return attempt.result_version_id


def test_writer_of_the_first_scene_sees_the_hero_state_of_book_1(tmp_path):
    repo, item, second, scene, cloth = second_book(tmp_path)
    context = build_context(repo, scene.id, 'brief', role())
    assert 'Халат' in context.user_text
    assert second.series_start_version_id in context.input_refs


def test_memory_stage_of_the_first_scene_extends_series_start(tmp_path):
    repo, item, second, scene, cloth = second_book(tmp_path)
    journal = load_memory(repo.read_text(write_scene_memory(repo, scene)))
    assert journal.source_prose_ids == [second.series_start_version_id, scene.heads['prose']]
    assert cloth.claim_id in {e.claim_id for e in journal.events}


def test_second_scene_passes_the_prefix_check(tmp_path):
    repo, item, second, scene, cloth = second_book(tmp_path)
    write_scene_memory(repo, scene)
    two = repo.create_scene(second.id, SceneCreate(title='Сцена 2', beats='Анна.', character_ids=['A']))
    p2 = prose(repo, two, 'Анна повернулася.')
    written = load_memory(repo.read_text(write_scene_memory(repo, repo.get_scene(two.id))))
    assert written.source_prose_ids == [second.series_start_version_id, scene.heads['prose'], p2.id]
    journal, _, _ = memory_for_manual_edit(repo.context_view(second.id), two.id)
    assert journal.source_prose_ids == [second.series_start_version_id, scene.heads['prose']]


def test_snapshot_is_source_number_zero(tmp_path):
    repo, item, second, scene, cloth = second_book(tmp_path)
    story = repo.get_story(second.id)
    numbers = memory_projection(repo.context_view(second.id), story, scene, repo.list_scenes(second.id), 'uk')[1]
    assert numbers == {second.series_start_version_id: 0}


def selection(section, number, **kw):
    item = MemoryItem(claim_id='c', section=section, owner=kw.get('owner'), line='— Подія', text='Подія',
                      character_ids=tuple(kw.get('cast', ())), slot=kw.get('slot'), source_scene=0)
    return SelectionInput(items=(item,), scene_id='s', scene_number=number, cast=tuple(kw.get('cast', ())),
                          tracked=tuple(kw.get('cast', ())), names={'A': 'Анна'})


def test_timeline_of_book_1_leaves_the_window_after_20_scenes():
    assert 'c' in select_memory(selection('timeline', 1), 10000).selected_claim_ids
    assert 'c' not in select_memory(selection('timeline', TIMELINE_WINDOW + 1), 10000).selected_claim_ids


def test_hero_state_of_book_1_is_recent_in_the_first_scenes():
    inp = selection('character_states', 1, owner='A', cast=['A'], slot='clothing')
    assert 'c' in select_memory(inp, 10000).selected_claim_ids


def test_retake_or_leaving_stales_brief_and_memory_of_scene_1(tmp_path):
    repo, item, second, scene, cloth = second_book(tmp_path)
    brief, memory = write_brief(repo, scene), write_scene_memory(repo, scene)
    assert not repo.get_version(brief).stale and not repo.get_version(memory).stale
    store.take_snapshot(repo, second.id, repo.get_story(second.id).revision)
    assert repo.get_version(brief).stale and repo.get_version(memory).stale
    repo2, item2, third, scene3, _ = second_book(tmp_path / 'other')
    brief3 = write_brief(repo2, scene3)
    store.set_story_series(repo2, third.id, None, None, None, repo2.get_story(third.id).revision)
    assert repo2.get_version(brief3).stale


def test_old_snapshot_without_the_selector_stales_after_a_snapshot_appears(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, _, _ = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second, scene = book(repo, 'Книга 2', cast=['A'])
    brief = write_brief(repo, scene)
    assert not any(s.field == 'series_start' for s in repo.get_version(brief).dependency_snapshot.selectors)
    into_series(repo, second, item.id, 2)
    assert repo.get_version(brief).stale


def test_book_outside_series_writes_no_series_selector(tmp_path):
    repo = Repository(tmp_path)
    story, scene = book(repo, 'Окрема', cast=[])
    brief = write_brief(repo, scene)
    assert not any(s.field == 'series_start' for s in repo.get_version(brief).dependency_snapshot.selectors)
    assert not repo.get_version(brief).stale


def test_memory_tab_names_the_previous_book_as_scene_0(tmp_path):
    from storygen.memory.forwarding import memory_view_from_view
    repo, item, second, scene, cloth = second_book(tmp_path)
    write_scene_memory(repo, scene)
    rows = memory_view_from_view(repo.context_view(second.id), scene.id)['rows']
    row = next(r for r in rows if r['claim_id'] == cloth.claim_id)
    assert (row['source_scene'], row['source_title']) == (0, 'Попередня книга серії')


def test_author_text_of_a_first_scene_depends_on_the_snapshot(tmp_path):
    from storygen.generation.dependencies import _manual_snapshot
    repo, item, second, scene, cloth = second_book(tmp_path)
    view = repo.context_view(second.id)
    snapshot = _manual_snapshot(repo, repo.get_scene(scene.id), 'prose')
    assert any(s.field == 'series_start' and s.expected == second.series_start_version_id for s in snapshot.selectors)
