"""SERIES-S10: the future section of a prequel's writing requests (neutral examples)."""
from storygen.application.writing_context import writing_context
from storygen.domain import SceneCreate
from storygen.generation.context import build_context
from storygen.generation.context_labels import label
from storygen.memory.future import future_lines, future_section
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository
from tests.memory.test_core_review import role
from tests.series.helpers import book, finished_book, into_series
from storygen.storage.snapshots import compare_snapshot
from tests.series.test_series_memory import write_brief, write_scene_memory

FUTURE = label('future_facts', 'uk')


def prequel_book(tmp_path, *, cast=('A',)):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, scenes, cloth = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    prequel, scene = book(repo, 'Приквел', cast=list(cast))
    later = repo.create_scene(prequel.id, SceneCreate(title='Сцена 2', beats='Анна.', character_ids=list(cast)))
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1),
                                     repo.get_story(prequel.id).revision)
    return repo, first, prequel, repo.get_scene(scene.id), repo.get_scene(later.id)


def keys(repo, story):
    return {fact['text']: fact['key'] for fact in store.start_facts(repo, story.id)}


def test_brief_and_draft_of_a_prequel_get_the_future_section(tmp_path):
    repo, first, prequel, scene, later = prequel_book(tmp_path)
    store.save_decisions(repo, prequel.id, {keys(repo, prequel)['Сусід пішов']: 'past'}, repo.get_story(prequel.id).revision)
    write_brief(repo, scene)
    write_scene_memory(repo, scene)
    for stage, target in (('brief', scene), ('draft', scene), ('brief', later)):
        text = build_context(repo, target.id, stage, role()).user_text
        section = text[text.index(FUTURE):text.index(label('memory_header', 'uk'))]
        assert 'Халат' in section and 'Сусід пішов' not in section


def test_memory_stage_has_no_future_section(tmp_path):
    repo, first, prequel, scene, later = prequel_book(tmp_path)
    assert FUTURE not in build_context(repo, scene.id, 'memory', role()).user_text


def test_limit_trims_with_a_note(tmp_path):
    future = [{'key': 'slot:A:clothing', 'category': 'character_states', 'text': 'Халат', 'character_ids': ['A']},
              {'key': 'claim:1', 'category': 'facts', 'text': 'Анна поїхала до моря', 'character_ids': []},
              {'key': 'claim:2', 'category': 'facts', 'text': 'Біля порту маяк', 'character_ids': []}]
    assert future_lines(future, {'A'}, {'A': 'Анна'}, 40) == (['- Анна: Халат', '- Анна поїхала до моря'], 1)
    repo, first, prequel, scene, later = prequel_book(tmp_path)
    section = future_section(repo, repo.get_story(prequel.id), scene, 'uk', 15)
    assert section == f"{FUTURE}\n- Анна: Халат\n{label('future_more', 'uk', count=1)}"
    assert future_section(repo, repo.get_story(prequel.id), scene, 'uk', 5) == f"{FUTURE}\n{label('future_more', 'uk', count=2)}"


def test_scene_without_cast_gets_records_without_heroes(tmp_path):
    lines, dropped = future_lines(
        [{'key': 'slot:A:clothing', 'category': 'character_states', 'text': 'Халат', 'character_ids': ['A']},
         {'key': 'claim:1', 'category': 'facts', 'text': 'Сусід пішов', 'character_ids': []}], set(), {'A': 'Анна'}, 1000)
    assert (lines, dropped) == (['- Сусід пішов'], 0)


def test_writing_context_future_changes_the_fingerprint(tmp_path):
    repo, first, prequel, scene, later = prequel_book(tmp_path)
    write_scene_memory(repo, scene)
    before = writing_context(repo, later.id)
    assert any('Халат' in line for line in before['future'])
    brief = write_brief(repo, later)
    store.save_decisions(repo, prequel.id, {keys(repo, prequel)['Халат']: 'past'}, repo.get_story(prequel.id).revision)
    write_scene_memory(repo, repo.get_scene(scene.id))  # the new snapshot stales scene 1's memory
    after = writing_context(repo, later.id)
    assert not any('Халат' in line for line in after['future'])
    assert after['context_fingerprint'] != before['context_fingerprint']
    # A later scene follows the future section itself, not only through the memory of the first scene.
    ref = repo.get_version(brief)
    assert any('series_future' in str(change) for change in compare_snapshot(repo.context_view(prequel.id),
                                                                            ref.dependency_snapshot))


def test_sequential_series_requests_are_unchanged(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second, scene = book(repo, 'Книга 2', cast=['A'])
    into_series(repo, second, item.id, 2)
    assert FUTURE not in build_context(repo, scene.id, 'brief', role()).user_text
    assert 'future' not in writing_context(repo, scene.id)
    ref = repo.get_version(write_brief(repo, repo.get_scene(scene.id)))
    assert FUTURE not in build_context(repo, scene.id, 'draft', role()).user_text
    assert not any(s.field == 'series_future' for s in ref.dependency_snapshot.selectors)


def test_mcp_fingerprint_without_a_future_is_as_before(tmp_path):
    # SERIES-001: a book without a future section keeps its MCP context fingerprint — an empty `future` is not hashed.
    from storygen.application.writing_context import _fingerprint, _read
    repo = Repository(tmp_path)
    story, scene = book(repo, 'Окрема', cast=['A'])
    scene, content, fingerprint = _read(repo, scene.id)
    assert 'future' not in content and fingerprint == _fingerprint(repo, scene, content)
