import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts'/'memory_retrieval_bench.py'
SECRETS=['Марія','Остап','халат','моря','ключ','дощ','хліб']


def run_cli(args):
    return subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,text=True,encoding='utf-8',cwd=ROOT)


def db_hash(data):
    return hashlib.sha256((data/'storygen.sqlite3').read_bytes()).hexdigest()


def test_cli_refuses_live_data():
    out=run_cli(['--data',str(ROOT/'data')])
    assert out.returncode==2 and out.stderr.strip()=='live_data' and out.stdout==''


def test_cli_refuses_dir_without_database(tmp_path):
    out=run_cli(['--data',str(tmp_path)])
    assert out.returncode==2 and out.stderr.strip()=='not_a_data_copy'


def test_cli_unknown_story(synthetic_repo):
    repo,_,_=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--story','zzz-none'])
    assert out.returncode==2 and out.stderr.strip()=='story_not_found'


def test_cli_output_shape_and_no_texts_or_claim_ids(synthetic_repo):
    repo,story_id,info=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','60','--context','32768,131072'])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    assert data['story']['scene_count']==4 and data['story']['protagonist_id']==info['maria']
    assert set(data['real'])=={'32768','131072'}
    assert {'full','all_active','full_a','structural[core=upper]','structural[core=lower]','structural_fts[core=upper]',
            'structural_fts[core=lower]'}==set(data['real']['32768']['conservative'])
    assert data['real']['131072']['conservative']['full']['target_recall']==1.0
    assert {'full','narrow'}==set(data['memory_stage']) and '60' in data['synthetic'] and data['control_cases'] is None
    claims=[info[k] for k in ('fact','state','thread','hidden')]
    for secret in SECRETS+claims+[story_id]:
        assert secret not in out.stdout


def test_cli_does_not_modify_database_and_is_deterministic(synthetic_repo):
    repo,_,_=synthetic_repo
    before=db_hash(repo.root)
    first=run_cli(['--data',str(repo.root),'--synthetic','40'])
    second=run_cli(['--data',str(repo.root),'--synthetic','40'])
    assert first.returncode==0 and first.stdout==second.stdout
    assert db_hash(repo.root)==before


def test_cli_control_cases(synthetic_repo,tmp_path):
    repo,story_id,info=synthetic_repo
    scenes=repo.list_scenes(story_id)
    cases=tmp_path/'cases.json'
    cases.write_text(json.dumps([{'scene_id':scenes[2].id,'claim_id':info['state']},{'scene_id':scenes[2].id,'claim_id':'nope'}]),encoding='utf-8')
    out=run_cli(['--data',str(repo.root),'--synthetic','','--control-cases',str(cases)])
    assert out.returncode==0,out.stderr
    hits=json.loads(out.stdout)['control_cases']['full']
    assert hits==[{'index':0,'hit':True,'reason':None},{'index':1,'hit':None,'reason':'missing_in_memory'}]


def test_cli_single_scene_story(tmp_path):
    from storygen.domain import SceneCreate, StoryCreate
    from storygen.storage.repository import Repository
    from tests.retrieval_bench.conftest import _save_scene
    repo=Repository(tmp_path/'data');story=repo.create_story(StoryCreate(title='Одна'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена 1'))
    _save_scene(repo,scene,'Тиша.',[dict(claim_id='a',operation='add',category='facts',text='Тихо',quote='Тиша.')])
    out=run_cli(['--data',str(repo.root),'--synthetic',''])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    assert data['story']['scene_count']==1 and data['growth']=={}


def test_cli_tokenizer_flag(synthetic_repo):
    repo,_,_=synthetic_repo
    data=json.loads(run_cli(['--data',str(repo.root),'--synthetic','','--tokenizer','claude']).stdout)
    assert data['params']['tokenizer']=='claude' and data['params']['chars_per_token']==round(238096/35122/2.96,3)
    assert run_cli(['--data',str(repo.root),'--tokenizer','nope']).returncode==2


def test_growth_is_not_budget_clipped(synthetic_repo):
    repo,_,_=synthetic_repo
    small=json.loads(run_cli(['--data',str(repo.root),'--synthetic','','--context','9000']).stdout)['growth']
    large=json.loads(run_cli(['--data',str(repo.root),'--synthetic','','--context','1000000']).stdout)['growth']
    assert small==large


def _pair_files(tmp_path,story_id,info,annotate=True):
    pairs=tmp_path/'pairs.json'
    pairs.write_text(json.dumps({'pairs':[{'id':'p1','repeat':3},{'id':'p2','repeat':2}],'controls':[{'id':'k1','repeat':4}]}),encoding='utf-8')
    ann=tmp_path/'ann.json'
    stories={story_id:{'p1':[info['state']],'p2':[info['fact']],'k1':[info['fact']]}} if annotate else {}
    ann.write_text(json.dumps({'stories':stories}),encoding='utf-8')
    return ['--pairs',str(pairs),'--pairs-annotation',str(ann)]


def test_budget_steps_section_present(synthetic_repo):
    repo,_,_=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','','--budget-steps','1.0,0.5'])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    assert set(data['budget_steps'])=={'1.0','0.5'}
    steps=data['budget_steps']['0.5']
    assert {'full','structural_fts[core=lower]'}<=set(steps)
    assert 'target_recall' in steps['full'] and 'pairs' not in steps['full']
    assert 'pairs' not in data and 'ranking' not in data
    base=json.loads(run_cli(['--data',str(repo.root),'--synthetic','']).stdout)
    assert 'budget_steps' not in base and set(base)<=set(data)


def test_pairs_section_counts_only(synthetic_repo,tmp_path):
    repo,story_id,info=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','','--budget-steps','0.75',*_pair_files(tmp_path,story_id,info)])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    summary=data['pairs']['full']
    assert summary['pair']['total']==2 and summary['pair']['hit']==2 and summary['control']['total']==1
    assert data['budget_steps']['0.75']['full']['pairs']['pair']['total']==2
    for secret in SECRETS+[info[k] for k in ('fact','state','thread','hidden')]+[story_id]:
        assert secret not in out.stdout


def test_ranking_section_has_bm25(synthetic_repo,tmp_path):
    repo,story_id,info=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','',*_pair_files(tmp_path,story_id,info)])
    assert out.returncode==0,out.stderr
    data=json.loads(out.stdout)
    ranking=data['ranking']
    assert set(ranking['bm25'])=={'pair','control'} and ranking['bm25']['pair']['total']==2
    layers=ranking['layers']['structural_fts[core=upper]']
    assert 'not_selected' in layers and sum(layers.values())==2
    assert 'not_selected' in ranking['layers_control']['structural_fts[core=upper]']
    assert set(ranking['layers'])=={'structural_fts[core=upper]','structural_fts[core=lower]'}
    assert info['fact'] not in out.stdout


def test_pairs_without_annotated_story_is_empty(synthetic_repo,tmp_path):
    repo,story_id,info=synthetic_repo
    out=run_cli(['--data',str(repo.root),'--synthetic','',*_pair_files(tmp_path,story_id,info,annotate=False)])
    assert out.returncode==0,out.stderr
    assert json.loads(out.stdout)['pairs']['full']['pair']['total']==0
