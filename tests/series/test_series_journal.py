"""SERIES-S02: the start snapshot is scene 0 of the book's memory (neutral examples)."""
import json

import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.memory.journal import MemoryJournal, _add_event, replay_memory, validate_memory_journal
from storygen.memory.series_start import SERIES_MARKER, inherit_journal, read_series_start, series_start_payload, source_number
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository

P1, P2 = 'p1', 'p2'
TEXTS = {P1: 'Анна в халаті. Вона мовчить. Хто стукав у двері?', P2: 'Анна вдягла пальто. Сусід пішов.'}


def source_journal():
    cloth = _add_event('character_states', 'Халат', P1, 'Анна в халаті.', 0, ['A'], slot='clothing')
    thread = _add_event('open_threads', 'Хто стукав?', P1, 'Хто стукав у двері?', 0, supporting=['Вона мовчить.'])
    secret = _add_event('character_states', 'Таємниця', P2, None, 0, ['A'], slot='carried', source_kind='author')
    later = _add_event('facts', 'Сусід пішов', P2, 'Анна в халаті.', 0, evidence_version_id=P1)
    return MemoryJournal(schema_version=3, source_prose_ids=[P1, P2], events=[cloth, thread, secret, later])


def test_inherited_journal_keeps_kinds_quotes_and_ids():
    journal = source_journal()
    text, inherited = inherit_journal(journal, TEXTS)
    assert inherited.source_prose_ids == [SERIES_MARKER]
    assert [(e.event_id, e.claim_id, e.source_kind, e.quote, e.supporting_quotes, e.slot) for e in inherited.events] == \
        [(e.event_id, e.claim_id, e.source_kind, e.quote, e.supporting_quotes, e.slot) for e in journal.events]
    assert {e.source_version_id for e in inherited.events} == {SERIES_MARKER}
    assert [e.evidence_version_id for e in inherited.events] == [None, None, None, SERIES_MARKER]
    assert {k: v.text for k, v in replay_memory(inherited).items()} == {k: v.text for k, v in replay_memory(journal).items()}


def test_inherited_quotes_are_in_the_text():
    text, inherited = inherit_journal(source_journal(), TEXTS)
    payload = series_start_payload(text, inherited, {'source_story_id': 's1'})
    data = read_series_start(payload, 'v-start')
    assert data.journal.source_prose_ids == ['v-start'] and data.source['source_story_id'] == 's1'
    validate_memory_journal(data.journal, {'v-start': data.text})


def test_scene_journal_extends_series_start():
    text, inherited = inherit_journal(source_journal(), TEXTS)
    data = read_series_start(series_start_payload(text, inherited, {}), 'v-start')
    own = _add_event('facts', 'Анна вийшла', 'p3', 'Анна вийшла.', 0)
    scene = MemoryJournal(schema_version=3, source_prose_ids=['v-start', 'p3'], events=data.journal.events + [own])
    validate_memory_journal(scene, {'v-start': data.text, 'p3': 'Анна вийшла.'})


def book_with_start(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга 2'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна.'))
    text, inherited = inherit_journal(source_journal(), TEXTS)
    start = repo.save_version(story.id, None, 'series_start', series_start_payload(text, inherited, {}), [])
    prose = repo.save_version(story.id, scene.id, 'manual', 'Анна вийшла.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    data = read_series_start(repo.read_text(start.id), start.id)
    return repo, story, scene, start, prose, data


def save_memory(repo, story, scene, sources, events):
    journal = MemoryJournal(schema_version=3, source_prose_ids=sources, events=events)
    memory = repo.save_version(story.id, scene.id, 'memory', journal.model_dump_json(), sources)
    return memory


def test_integrity_accepts_series_start_only_at_position_0(tmp_path):
    repo, story, scene, start, prose, data = book_with_start(tmp_path)
    own = _add_event('facts', 'Анна вийшла', prose.id, 'Анна вийшла.', 0)
    save_memory(repo, story, scene, [start.id, prose.id], data.journal.events + [own])
    assert check_integrity(repo.root).ok, check_integrity(repo.root).issues
    wrong = _add_event('facts', 'Анна вийшла', start.id, 'Анна вийшла.', 1)
    first = _add_event('facts', 'Перше', prose.id, 'Анна вийшла.', 2)
    save_memory(repo, story, scene, [prose.id, start.id], [first, wrong])
    assert [i.code for i in check_integrity(repo.root).issues] == ['invalid_memory']


def test_source_number_is_zero_for_series_start(tmp_path):
    repo, story, scene, start, prose, data = book_with_start(tmp_path)
    assert source_number(repo.get_version(start.id), {scene.id: 1}) == 0
    assert source_number(repo.get_version(prose.id), {scene.id: 1}) == 1


def test_payload_keeps_the_marker(tmp_path):
    text, inherited = inherit_journal(source_journal(), TEXTS)
    raw = json.loads(series_start_payload(text, inherited, {}))
    assert raw['journal']['source_prose_ids'] == [SERIES_MARKER] and raw['schema_version'] == 1
    with pytest.raises(ValueError):
        read_series_start(json.dumps({**raw, 'schema_version': 99}), 'v')
