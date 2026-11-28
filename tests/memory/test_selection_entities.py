"""MEMORY-ENTITIES-S07: the overlay in the selection layers and the narrowed catalog."""
import pytest

from storygen.domain import MemoryEntityMark
from storygen.memory.entities import EntityResolver
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.selection import classify, narrow_catalog
from tests.memory.test_selection import NAMES, inp, item, layer_of, scene_items


def M(p=(),l=(),s='model'):
    return MemoryEntityMark(participant_ids=list(p),location_ids=list(l),source=s)


def resolver(marks=None,cards=('h','a','x'),merged=None):
    return EntityResolver(marks or {},frozenset(cards),merged or {})


def with_participants(base,ids):
    from dataclasses import replace
    return replace(base,participant_ids=tuple(ids))


@pytest.mark.req('MEMORY-ENTITIES')
def test_model_mark_puts_a_thread_without_participants_into_threads():
    thread=item('t_x','open_threads','Скарб у горах',scene=3)
    assert layer_of(classify(inp([thread])))['t_x']=='fts'
    marked=resolver({'t_x':M(['a'])}).items([thread])
    assert layer_of(classify(inp(marked)))['t_x']=='threads'


@pytest.mark.req('MEMORY-ENTITIES')
def test_overlay_location_puts_a_fact_into_place():
    fact=item('f_l','facts','Маяк збудовано 1890 року',scene=1)
    marked=resolver({'f_l':M([],['l1'])}).items([fact])
    from dataclasses import replace
    base=inp(marked);selection=replace(base,place=frozenset({'l1'}))
    assert layer_of(classify(selection))['f_l']=='place'
    assert layer_of(classify(inp([fact])))['f_l']!='place'


@pytest.mark.req('MEMORY-ENTITIES')
def test_deleted_participant_falls_back_to_names():
    fact=with_participants(item('f_g','facts','Оля живе на Подолі',scene=1),['gone'])
    assert layer_of(classify(inp([fact])))['f_g']=='fts'
    assert layer_of(classify(inp(resolver().items([fact]))))['f_g']=='facts'


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_empty_override_falls_back_to_names():
    fact=with_participants(item('f_e','facts','Оля живе на Подолі',scene=1),['x'])
    assert layer_of(classify(inp([fact])))['f_e']=='fts'
    assert layer_of(classify(inp(resolver({'f_e':M([],[],'author')}).items([fact]))))['f_e']=='facts'


@pytest.mark.req('MEMORY-ENTITIES')
def test_old_timeline_with_an_overlay_participant_goes_to_past():
    old=item('tl_o','timeline','Ганна приїхала',scene=2)
    assert layer_of(classify(inp([old],number=40)))['tl_o']=='timeline'
    assert layer_of(classify(inp(resolver({'tl_o':M(['a'])}).items([old]),number=40)))['tl_o']=='past'


@pytest.mark.req('MEMORY-ENTITIES')
def test_record_without_any_entities_is_classified_as_before():
    assert layer_of(classify(inp(resolver().items(scene_items()))))==layer_of(classify(inp()))


def journal_events():
    events=[_add_event('facts','Маяк збудовано 1890 року','v1','цитата',0),
        _add_event('character_states','Петро чекає листа','v1','цитата',1,['x']),
        _add_event('facts','Скеля стоїть біля бухти','v1','цитата',2)]
    return MemoryJournal(schema_version=4,source_prose_ids=['v1'],events=events),events


def narrow(journal,entities=None,place=()):
    return narrow_catalog(journal,['a'],['h'],NAMES,'',30,{'v1':1},None,place=place,entities=entities)


@pytest.mark.req('MEMORY-ENTITIES')
def test_narrow_catalog_keeps_facts_and_states_by_the_overlay():
    journal,events=journal_events()
    fact,state,other=(e.claim_id for e in events)
    marks={fact:M(['a']),state:M([],['l1'])}
    plain=narrow(journal)
    assert fact not in plain.keep and state not in plain.keep
    kept=narrow(journal,resolver(marks),place={'l1'}).keep
    assert fact in kept and state in kept and other not in kept
