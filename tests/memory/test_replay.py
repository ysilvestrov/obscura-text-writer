import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from storygen.memory.journal import MemoryJournal
from storygen.memory.replay import collect, replay_response, summarize, v2_as_v3
from tests.memory.wire_helpers import v3_response

ROOT=Path(__file__).resolve().parents[2]
PROSE='Секрет-рядок один.\nСекрет-рядок два.'


def frags(wire=None,allowed=()):
    f={'previous_memory':MemoryJournal().model_dump_json(),'memory_allowed_character_ids':json.dumps(list(allowed))}
    if wire:f['memory_wire_version']=wire
    return f


def v2(evidence,text='Т'):
    return json.dumps({'schema_version':2,'operations':[{'action':'add','category':'facts','claim_id':None,'text':text,'character_ids':[],'evidence_id':evidence}]})


def test_v2_as_v3_splits_evidence_and_drops_meta():
    v3=v2_as_v3({'schema_version':2,'operations':[
        {'action':'add','category':'facts','claim_id':None,'text':'Т','character_ids':[],'evidence_id':'f000001, f000002'},
        {'action':'update','category':'open_threads','claim_id':'mc_t','text':'Н','character_ids':['c1'],'evidence_id':'f000003'}]})
    assert v3['facts']['add']==[{'text':'Т','evidence_ids':['f000001','f000002']}]
    assert v3['open_threads']['update']==[{'claim_id':'mc_t','text':'Н','evidence_ids':['f000003']}]
    assert v3['schema_version']==3 and v3['timeline']=={'add':[]}


def test_replay_counts_multi_evidence_as_fixed_by_v3():
    r=replay_response(v2('f000001,f000002'),frags(),'v1',PROSE)
    assert r['wire']==2 and r['as_is']=='fail' and 'evidence_unknown' in r['as_is_codes'] and r['as_v3']=='pass'


def test_replay_v3_response_uses_wire_from_fragments():
    raw=v3_response(facts_add=[{'text':'Т','evidence_ids':['f000001']}])
    r=replay_response(raw,frags('3'),'v1',PROSE)
    assert r['wire']==3 and r['as_is']=='pass' and r['as_v3'] is None


def test_replay_json_error_is_counted():
    r=replay_response('{не json',frags(),'v1',PROSE)
    assert r['as_is']=='json' and r['as_v3']=='json'
    assert summarize([r])['as_is']['json']==1


def make_db(tmp_path,attempts):
    data=tmp_path/'data';(data/'prose').mkdir(parents=True);(data/'prose'/'v1.txt').write_text(PROSE,encoding='utf-8')
    db=data/'s.sqlite3';c=sqlite3.connect(db)
    c.execute('CREATE TABLE stage_attempts(id TEXT, state TEXT, payload TEXT)');c.execute('CREATE TABLE versions(id TEXT, payload TEXT)')
    c.execute('INSERT INTO versions VALUES(?,?)',('v1',json.dumps({'relative_path':'prose'})))
    for i,(raw,fragments) in enumerate(attempts):
        partial=f'p{i}.txt'
        if raw is not None:(data/partial).write_text(raw,encoding='utf-8')
        payload={'stage':'memory','state':'failed','story_id':'СЕКРЕТ-ТВІР','partial_path':partial,
                 'context':{'settings':{'memory_mode':'evidence_delta'},'fragments':fragments}}
        c.execute('INSERT INTO stage_attempts VALUES(?,?,?)',(f'a{i}','failed',json.dumps(payload)))
    c.commit();c.close();return db,data


def test_summarize_and_cli_print_no_texts(tmp_path):
    good=dict(frags(),expected_source_prose_ids='["v1"]')
    secret=v2('f000001,f000002','СЕКРЕТ-ВІДПОВІДІ')
    db,data=make_db(tmp_path,[(secret,good),(None,good),(secret,frags())])
    out=subprocess.run([sys.executable,str(ROOT/'scripts'/'memory_replay.py'),'--db',str(db),'--data',str(data)],
                       cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert out.returncode==0,out.stderr
    for marker in ('СЕКРЕТ','Секрет','v1','a0','mc_'):assert marker not in out.stdout
    result=json.loads(out.stdout)
    assert result['replayed']==1 and result['fixed_by_v3']==1
    assert result['as_is']['fail']==1 and result['as_v3']['pass']==1 and result['as_is_codes']=={'evidence_unknown':1}
    assert result['skipped']['no_raw']==1 and result['skipped']['no_bounds']==1


def test_attempt_without_partial_is_skipped_not_crash(tmp_path):
    db,data=make_db(tmp_path,[(None,dict(frags(),expected_source_prose_ids='["v1"]'))])
    assert summarize(collect(db,data))['skipped']['no_raw']==1
