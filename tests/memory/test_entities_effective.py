"""MEMORY-ENTITIES-S05: the overlay mark and the effective participants and locations of a memory record."""
import pytest
from pydantic import ValidationError

from storygen.domain import MemoryEntityMark, Story
from storygen.memory.entities import EntityResolver, effective
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import MemoryItem, candidate_claim_ids, candidate_events


def M(p=(), l=(), s='model'):
    return MemoryEntityMark(participant_ids=list(p), location_ids=list(l), source=s)


K = frozenset({'c1', 'c2'})


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_mark_wins_over_the_event_even_when_empty():
    e = effective('facts', ['c2'], [], M([], [], 'author'), K, {})
    assert e.participant_ids == () and e.participants_from == 'author'


@pytest.mark.req('MEMORY-ENTITIES')
def test_event_wins_over_a_model_mark_and_model_fills_the_gap():
    e = effective('facts', ['c1'], [], M(['c2'], ['l1']), K, {})
    assert (e.participant_ids, e.participants_from) == (('c1',), 'event')
    assert (e.location_ids, e.locations_from) == (('l1',), 'model')


@pytest.mark.req('MEMORY-ENTITIES')
def test_unknown_participant_is_dropped_before_the_non_empty_check():
    assert effective('facts', ['gone'], [], M(['c2']), K, {}).participant_ids == ('c2',)
    assert effective('facts', ['gone'], [], None, K, {}).participant_ids == ()


@pytest.mark.req('MEMORY-ENTITIES')
def test_state_takes_only_locations_from_the_mark():
    e = effective('character_states', [], [], M(['c1'], ['l1']), K, {})
    assert e.participant_ids == () and e.location_ids == ('l1',)


@pytest.mark.req('MEMORY-ENTITIES')
def test_locations_follow_merges():
    assert effective('facts', [], ['old'], None, K, {'old': 'new'}).location_ids == ('new',)


@pytest.mark.req('MEMORY-ENTITIES')
def test_source_is_the_weakest_contributor():
    assert effective('facts', ['c1'], [], M([], ['l1']), K, {}).source == 'model'
    assert effective('facts', ['c1'], [], None, K, {}).source == 'event'
    assert effective('facts', [], [], None, K, {}).source is None
    assert effective('facts', ['c1'], ['l1'], M([], [], 'author'), K, {}).source == 'author'


def item(participants=('gone',), section='facts'):
    return MemoryItem(claim_id='f1', section=section, owner=None, line='l', text='t', character_ids=(), slot=None,
        source_scene=1, location_ids=(), participant_ids=tuple(participants))


@pytest.mark.req('MEMORY-ENTITIES')
def test_resolver_replaces_item_entities_and_bare_ignores_marks():
    resolver = EntityResolver({'f1': M(['c1'], ['l1'])}, K, {})
    assert resolver.item(item()).participant_ids == ('c1',)
    assert resolver.item(item()).location_ids == ('l1',)
    assert resolver.bare().item(item()).participant_ids == ()
    assert resolver.items([item()])[0].participant_ids == ('c1',)
    # the core section is a character state: no participants, only locations
    core = resolver.item(item(section='core'))
    assert core.participant_ids == () and core.location_ids == ('l1',)


@pytest.mark.req('MEMORY-ENTITIES')
def test_story_without_marks_keeps_its_payload_byte_for_byte():
    assert 'memory_entities' not in Story(id='s', title='T').model_dump_json()
    assert 'memory_entities' in Story(id='s', title='T', memory_entities={'f1': M(['c1'])}).model_dump_json()


@pytest.mark.req('MEMORY-ENTITIES')
def test_mark_rejects_duplicates_and_too_many_marks():
    with pytest.raises(ValidationError, match='Некоректна розмітка сутностей'):
        M(['c1', 'c1'])
    with pytest.raises(ValidationError):
        M([''])
    marks = {f'f{i}': M() for i in range(20001)}
    with pytest.raises(ValidationError):
        Story(id='s', title='T', memory_entities=marks)


@pytest.mark.req('MEMORY-ENTITIES')
def test_candidate_events_cover_candidate_claim_ids():
    fact = _add_event('facts', 'Ключ у коморі', 'p1', 'q', 0)
    stamp = _add_event('timeline', 'Прийшла зима', 'p1', 'q', 1)
    thread = _add_event('open_threads', 'Хто взяв ключ', 'p1', 'q', 2)
    close = thread.model_copy(update={'event_id': 'close', 'operation': 'retire'})
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[fact, stamp, thread, close])
    found = candidate_events(journal)
    assert set(found) == candidate_claim_ids(journal)
    assert {fact.claim_id, stamp.claim_id, thread.claim_id} <= set(found)
