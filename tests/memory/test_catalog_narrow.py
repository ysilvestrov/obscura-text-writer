"""MEMORY-SELECT-S07: the narrowed memory-stage catalog and its schema bounds are one set of claims (#60, PR 2)."""
import json

from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import memory_catalog_v4
from storygen.memory.selection import NARROW_FTS_STATES, narrow_catalog
from storygen.memory.wire_v4 import check_v4, schema_bounds_v4
from tests.memory.test_wire_v4 import answer, chg, core, threads

SLOT=_add_event('character_states','Синій халат','p1','q',0,['h'],slot='clothing')
THREAD=_add_event('open_threads','Хто стукав?','p1','q',0)
HERO=_add_event('character_states','Ганна втомлена','p1','q',0,['h'])
RAIN=_add_event('character_states','Іде дощ','p1','q',0)
AWAY=[_add_event('character_states',f'Петро далеко номер {n}','p1','q',n,['x']) for n in range(30)]
GUN=_add_event('character_states','Петро ховає пістолет','p1','q',99,['x'])
FACT_HERO=_add_event('facts','Ганна народилася в Одесі','p1','q',0)
FACT_FAR=_add_event('facts','Маяк збудовано давно','p1','q',0)
OLD=_add_event('timeline','Давня подія','p1','q',0)
NEW=_add_event('timeline','Нова подія','p2','q',0)
JOURNAL=MemoryJournal(schema_version=3,source_prose_ids=['p1','p2'],events=[SLOT,THREAD,HERO,RAIN,*AWAY,GUN,FACT_HERO,FACT_FAR,OLD,NEW])
NAMES={'h':'Ганна'}
PROSE='Ганна вдягла пальто.\nУ кишені пістолет.\nСтукав сусід.'


def narrow(prose=PROSE):
    return narrow_catalog(JOURNAL,['h'],['h'],NAMES,prose,31,{'p1':1,'p2':30})


def test_narrow_keeps_core_threads_cast_general_prose_states_facts_and_recent_timeline():
    result=narrow()
    assert {SLOT.claim_id,THREAD.claim_id,HERO.claim_id,RAIN.claim_id,GUN.claim_id,FACT_HERO.claim_id,NEW.claim_id}<=result.keep
    assert not {FACT_FAR.claim_id,OLD.claim_id}&result.keep
    assert result.hidden==len(JOURNAL.events)-len(result.keep)
    assert result.mutable_shown==3 and result.immutable_shown==2


def test_prose_ranked_states_are_capped():
    shown=narrow('Петро далеко номер '*5).keep&{e.claim_id for e in AWAY+[GUN]}
    assert len(shown)==NARROW_FTS_STATES


def test_catalog_and_bounds_share_the_kept_claims():
    keep=set(narrow().keep)
    full=json.loads(memory_catalog_v4(JOURNAL,['h'],NAMES))
    small=json.loads(memory_catalog_v4(JOURNAL,['h'],NAMES,keep=keep))
    assert memory_catalog_v4(JOURNAL,['h'],NAMES,keep=None)==memory_catalog_v4(JOURNAL,['h'],NAMES)
    assert small['core']==full['core'] and small['threads']==full['threads']
    assert len(small['mutable'])<len(full['mutable']) and len(small['immutable'])<len(full['immutable'])
    bounds=schema_bounds_v4(JOURNAL,PROSE,['h'],['h'],{'h':False},keep=keep)
    assert bounds['mutable']['character_states']==[m['claim_id'] for m in small['mutable']]
    assert schema_bounds_v4(JOURNAL,PROSE,['h'],['h'],{'h':False},keep=None)==schema_bounds_v4(JOURNAL,PROSE,['h'],['h'],{'h':False})


def test_update_outside_the_narrowed_catalog_is_rejected():
    keep=set(narrow().keep)
    bounds=schema_bounds_v4(JOURNAL,PROSE,['h'],['h'],{'h':False},keep=keep)
    hidden=AWAY[0].claim_id
    assert hidden not in keep
    data=answer(core(),{THREAD.claim_id:threads()[next(iter(threads()))]},character_states_update=[chg(hidden,'Петро повернувся',['f000001'])])
    assert ('character_states.update[0]','target_unknown') in [tuple(v) for v in check_v4(data,JOURNAL,bounds)]
