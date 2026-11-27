import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


# ---- vector models in the CLI (Task 7): in-process, FakeEmbedder through the embedder factory ----

CLOUD_ENV=('AZURE_OPENAI_ENDPOINT','AZURE_OPENAI_API_KEY','AZURE_OPENAI_EMBEDDING_DEPLOYMENT','AZURE_OPENAI_API_VERSION')


def _bench():
    import memory_retrieval_bench
    return memory_retrieval_bench


def _patch_factory(monkeypatch,built,cls=None):
    bench=_bench()

    def make(key,spec,args):
        from memory_bench.embeddings import FakeEmbedder
        embedder=(cls or FakeEmbedder)();embedder.key=key;built.append(key)
        return embedder
    monkeypatch.setattr(bench,'make_inner_embedder',make)


@pytest.fixture
def cache_dir():
    """The vector cache must lie outside the repository; pytest's tmp_path may be inside it."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='rb-cache-') as tmp:
        yield Path(tmp)


def _vec_args(repo,cache_dir,*extra):
    return ['--data',str(repo.root),'--synthetic','','--cache-dir',str(cache_dir),*extra]


def _report(args):
    bench=_bench();parsed=bench.build_parser().parse_args(args)
    bench.set_tokenizer(parsed.tokenizer)
    return bench.run(parsed)


def _set_cloud_env(monkeypatch,value='x'):
    for name in CLOUD_ENV:
        monkeypatch.setenv(name,value)


def test_vector_variants_in_real_and_steps(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,info=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    report,error=_report(_vec_args(repo,cache_dir,'--vector-models','e5-base','--context','32768','--budget-steps','0.5',*_pair_files(tmp_path,story_id,info)))
    assert error is None and built==['e5-base']
    vec={f'structural_{k}[e5-base][core={m}]' for k in ('vec','hybrid') for m in ('upper','lower')}
    assert vec<=set(report['real']['32768']['realistic']) and vec<=set(report['real']['32768']['conservative'])
    assert vec<=set(report['budget_steps']['0.5']) and vec<=set(report['pairs'])
    assert 'pairs' in report['budget_steps']['0.5']['structural_vec[e5-base][core=upper]']
    assert {'vec[e5-base]','hybrid[e5-base]','bm25'}<=set(report['ranking'])
    assert report['ranking']['vec[e5-base]']['pair']['total']==2
    assert vec<=set(report['ranking']['layers']) and vec<=set(report['ranking']['layers_control'])
    layers=report['ranking']['layers']['structural_vec[e5-base][core=upper]']
    assert sum(layers.values())==2 and 'fts' not in layers
    section=report['vector']['e5-base']
    assert section['model_id']=='fake' and section['dim']==16 and section['threads']==1
    assert section['cache_misses']>0 and section['cache_hits']>0 and section['cache_bytes']>0
    assert section['index_seconds']>=section['index_seconds_cold']>=0 and section['weights_bytes'] is None
    assert set(section['libs'])=={'numpy','torch','sentence_transformers','transformers'}
    assert 'tokens' not in section and section['repro_identical_share'] is None


def test_synthetic_has_no_vector_variants(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,info=synthetic_repo
    _patch_factory(monkeypatch,[])
    cases=tmp_path/'cases.json';cases.write_text(json.dumps([{'scene_id':'x','claim_id':'y'}]),encoding='utf-8')
    args=_vec_args(repo,cache_dir,'--vector-models','e5-base','--control-cases',str(cases))
    args[args.index('--synthetic')+1]='60'
    report,error=_report(args)
    assert error is None

    def has_vec(section):
        return any('_vec[' in k or '_hybrid[' in k for k in section)
    assert not has_vec(report['synthetic']['60']['32768']['conservative']) and not has_vec(report['growth'])
    assert not has_vec(report['control_cases']) and not has_vec(report['product']['32768']['realistic'])
    assert not has_vec(report['memory_stage']) and has_vec(report['real']['32768']['realistic'])


def test_no_vector_models_has_no_vector_section(synthetic_repo):
    repo,_,_=synthetic_repo
    report,error=_report(['--data',str(repo.root),'--synthetic',''])
    assert error is None and 'vector' not in report


def test_cloud_model_without_flag_refused(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    repo,_,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    for extra in ([],['--cloud-stories','']):
        assert _bench().main(_vec_args(repo,cache_dir,'--vector-models','e5-base,azure-3-large',*extra))==2
        out=capsys.readouterr()
        assert out.err.strip()=='cloud_not_allowed' and out.out=='' and built==[]


def test_cloud_story_outside_allowlist_refused(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    assert _bench().main(_vec_args(repo,cache_dir,'--vector-models','azure-3-large','--cloud','--cloud-stories','zzz-,'))==2
    assert capsys.readouterr().err.strip()=='cloud_not_allowed' and built==[]


def test_cloud_config_missing(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    _set_cloud_env(monkeypatch)
    monkeypatch.delenv('AZURE_OPENAI_API_KEY')
    assert _bench().main(_vec_args(repo,cache_dir,'--vector-models','azure-3-large','--cloud','--cloud-stories',story_id))==2
    assert capsys.readouterr().err.strip()=='cloud_config_missing' and built==[]


def test_cloud_section_and_repro_none(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    from memory_bench.embeddings import FakeEmbedder
    repo,story_id,_=synthetic_repo

    class FakeCloud(FakeEmbedder):
        tokens,usd,latencies=120,0.0000156,[0.1,0.2,0.3,0.4]
    _patch_factory(monkeypatch,[],FakeCloud)
    _set_cloud_env(monkeypatch)
    report,error=_report(_vec_args(repo,cache_dir,'--vector-models','azure-3-large','--cloud','--cloud-stories',story_id,'--repro','--context','32768'))
    assert error is None
    section=report['vector']['azure-3-large']
    assert section['tokens']==120 and section['usd']==pytest.approx(0.0000156) and section['threads'] is None
    assert section['latency_ms']=={'p50':200.0,'p90':400.0} and section['repro_identical_share'] is None
    assert section['weights_bytes'] is None


def test_cloud_budget_maps_to_exit_2(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    from memory_bench.embeddings import FakeEmbedder
    repo,story_id,_=synthetic_repo

    class Over(FakeEmbedder):
        def embed(self,texts,kind):
            raise ValueError('cloud_budget')
    _patch_factory(monkeypatch,[],Over)
    _set_cloud_env(monkeypatch,'SECRET-VALUE')
    assert _bench().main(_vec_args(repo,cache_dir,'--vector-models','azure-3-large','--cloud','--cloud-stories',story_id))==2
    out=capsys.readouterr()
    assert out.err.strip()=='cloud_budget' and 'SECRET-VALUE' not in out.err+out.out


def test_vector_deps_missing_inside_repo_unknown_model(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    repo,_,_=synthetic_repo
    bench=_bench()

    def broken(key,spec,args):
        raise ImportError('sentence_transformers')
    monkeypatch.setattr(bench,'make_inner_embedder',broken)
    assert bench.main(_vec_args(repo,cache_dir,'--vector-models','e5-base'))==2
    assert capsys.readouterr().err.strip()=='vector_deps_missing'
    built=[];_patch_factory(monkeypatch,built)
    args=_vec_args(repo,cache_dir,'--vector-models','e5-base');args[args.index('--cache-dir')+1]=str(ROOT/'tmp-cache-test')
    assert bench.main(args)==2
    assert capsys.readouterr().err.strip()=='inside_repo' and built==[]
    assert bench.main(_vec_args(repo,cache_dir,'--vector-models','nope'))==2
    assert capsys.readouterr().err.strip()=='unknown_vector_model' and built==[]


def test_repro_identical_share_with_fake_is_one(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    report,error=_report(_vec_args(repo,cache_dir,'--vector-models','e5-base','--repro','--context','32768,65536'))
    assert error is None and report['vector']['e5-base']['repro_identical_share']==1.0
    assert built==['e5-base','e5-base']  # a NEW inner embedder for the re-run


def test_report_contains_no_texts(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    from memory_bench.extract import extract_story
    repo,story_id,info=synthetic_repo
    _patch_factory(monkeypatch,[])
    report,error=_report(_vec_args(repo,cache_dir,'--vector-models','e5-base','--repro','--budget-steps','0.5',*_pair_files(tmp_path,story_id,info)))
    assert error is None
    scenes,_=extract_story(repo,story_id,None)
    secrets={r.text for s in scenes for r in s.records}|{s.plan_text for s in scenes}|set(SECRETS)
    assert len(secrets)>10
    dumped=json.dumps(report,ensure_ascii=False)
    for text in secrets:
        assert text and text not in dumped


def test_repro_does_not_change_main_vector_metrics(synthetic_repo,tmp_path,monkeypatch):
    pytest.importorskip('numpy')
    repo,story_id,info=synthetic_repo
    _patch_factory(monkeypatch,[])
    runs=[]
    for flag in ([],['--repro']):
        with __import__('tempfile').TemporaryDirectory(prefix='rb-cache-') as tmp:
            report,error=_report(_vec_args(repo,Path(tmp),'--vector-models','e5-base','--context','32768',*flag))
        assert error is None
        runs.append(report['vector']['e5-base'])
    plain,repro=runs
    assert plain['repro_identical_share'] is None and repro['repro_identical_share']==1.0
    ignore={'repro_identical_share','index_seconds','index_seconds_cold','load_seconds'}
    assert {k:v for k,v in plain.items() if k not in ignore}=={k:v for k,v in repro.items() if k not in ignore}


def test_vector_load_failure_maps_to_code(synthetic_repo,tmp_path,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    repo,_,_=synthetic_repo;closed=[]
    from memory_bench.embeddings import FakeEmbedder
    bench=_bench()

    class Closable(FakeEmbedder):
        def close(self):
            closed.append(self.key)

    def factory(key,spec,args):
        if key=='bge-m3':
            raise OSError('offline: model not in cache')
        embedder=Closable();embedder.key=key
        return embedder
    monkeypatch.setattr(bench,'make_inner_embedder',factory)
    assert bench.main(_vec_args(repo,cache_dir,'--vector-models','e5-base,bge-m3'))==2
    out=capsys.readouterr()
    assert out.err.strip()=='vector_load_failed' and out.out=='' and closed==['e5-base']


def test_cloud_keys_match_models():
    pytest.importorskip('numpy')
    from memory_bench.embeddings import MODELS
    assert set(_bench().CLOUD_KEYS)=={k for k,m in MODELS.items() if m['kind']=='cloud'}


def test_truncate_base_missing(synthetic_repo,monkeypatch,capsys,cache_dir):
    pytest.importorskip('numpy')
    repo,_,_=synthetic_repo;built=[];_patch_factory(monkeypatch,built)
    assert _bench().main(_vec_args(repo,cache_dir,'--vector-models','nano-512'))==2
    out=capsys.readouterr()
    assert out.err.strip()=='truncate_base_missing' and out.out=='' and built==[]


def test_truncate_shares_base_model_and_cache(synthetic_repo,tmp_path,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,info=synthetic_repo;built=[];_patch_factory(monkeypatch,built)
    for order in ('nano-2048,nano-512','nano-512,nano-2048'):
        report,error=_report(_vec_args(repo,cache_dir,'--vector-models',order,'--context','32768'))
        assert error is None
        vec=report['vector']
        assert set(vec)=={'nano-2048','nano-512'} and vec['nano-512']['dim']==512
        assert vec['nano-512']['load_seconds']==0 and vec['nano-512']['model_id']==vec['nano-2048']['model_id']
        assert vec['nano-512']['weights_bytes']==vec['nano-2048']['weights_bytes']
    assert built==['nano-2048','nano-2048']
