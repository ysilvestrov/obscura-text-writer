import json

import pytest

from memory_bench.strategies import catalog_full_v4, catalog_narrow_v4
from storygen.memory.journal import MemoryJournal, _add_event
from tests.retrieval_bench.helpers import scene
from tests.retrieval_bench.test_cli import SECRETS, run_cli

SLOT=_add_event('character_states','Халат','p1','q',0,['c1'],slot='clothing')
THREAD=_add_event('open_threads','Хто стукав','p1','q',0)
NEAR=_add_event('character_states','Марія втомлена','p1','q',0,['c1'])
FAR=[_add_event('character_states',f'Ганна далеко {n}','p1','q',n,['c3']) for n in range(25)]
JOURNAL=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[SLOT,THREAD,NEAR,*FAR])


def v4_scene(targets):
    base=scene(targets=targets)
    data={'journal':JOURNAL,'cast':['c1'],'tracked':['c1'],'names':{'c1':'Марія'},'prose':'Марія вдома.','number':2,'source_numbers':{'p1':1}}
    return type(base)(**{**base.__dict__,'catalog_v4':data})


def test_narrow_v4_keeps_core_threads_and_cast_states_and_hides_the_rest():
    s=v4_scene({SLOT.claim_id,THREAD.claim_id,NEAR.claim_id})
    full,narrow=catalog_full_v4(s),catalog_narrow_v4(s)
    assert {SLOT.claim_id,THREAD.claim_id,NEAR.claim_id}<=set(narrow.record_ids)
    assert set(full.record_ids)-set(narrow.record_ids)=={e.claim_id for e in FAR}
    assert narrow.chars<full.chars


def test_absent_tracked_slot_is_not_a_reachable_target():
    absent=_add_event('character_states','Червоне пальто','p1','q',0,['c2'],slot='clothing')
    base=scene(targets={absent.claim_id})
    data={'journal':MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[SLOT,absent]),'cast':['c1'],
          'tracked':['c1','c2'],'names':{'c1':'Марія','c2':'Оля'},'prose':'Марія вдома.','number':2,'source_numbers':{'p1':1}}
    s=type(base)(**{**base.__dict__,'catalog_v4':data})
    for build in (catalog_full_v4,catalog_narrow_v4):
        assert set(build(s).record_ids)=={SLOT.claim_id}


def test_catalog_v4_requires_real_data():
    with pytest.raises(ValueError):
        catalog_narrow_v4(scene())


def test_cli_reports_memory_stage_v4_apart(synthetic_repo):
    repo,story_id,_=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','','--context','32768'])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    assert set(data['memory_stage_v4'])=={'full','narrow'} and {'full','narrow'}==set(data['memory_stage'])
    for secret in SECRETS+[story_id]:
        assert secret not in out.stdout
