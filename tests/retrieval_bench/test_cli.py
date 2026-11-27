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


# ---- --paraphrases (Task 4): set.json and owner-check.json written the way scripts/rag_paraphrases.py writes them ----

@pytest.fixture
def para_dir():
    """Outside the repository (pytest's tmp_path may be inside it)."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='rb-para-') as tmp:
        yield Path(tmp)


NEUTRAL={'syn':'Жовтий човник пливе','desc':'Тиша огортає подвір’я'}  # share no stem with any record of the fixtures


def level_queries(frame,names):
    """Queries the way the generator keeps them: same = a mention with the record's words, syn/desc = a neutral sentence;
    the status comes from level_ok over all story names (a record with < 2 content words fails 'same')."""
    from memory_bench.paraphrase import LEVELS,Query,_sha,level_ok
    out=[]
    for r in frame:
        for level in LEVELS:
            text=f'Згадка: {r.text}' if level=='same' else NEUTRAL[level]
            out.append(Query(r.claim_id,level,text,'ok' if level_ok(level,text,r.text,names) else 'rejected',_sha(r.text)))
    return out


def write_para(folder,scenes,story_id,queries,owner=True,owner_k=20,meta_over=None,owner_seed=0,owner_count=None):
    """set.json and owner-check.json (all verdicts yes) as scripts/rag_paraphrases.py writes them; a meta_over value
    of ... drops that meta key."""
    from memory_bench.paraphrase import FRAME_PARAMS,LEVELS,manifest,owner_sample,sampling_frame,snapshot_hash,write_owner_file
    frame=sampling_frame(scenes,FRAME_PARAMS)
    meta={'story':story_id,'protagonist':scenes[0].protagonist,'seed':0,'n':len(frame),'model':'m','prompt_id':'p',
          'levels':list(LEVELS),'owner_k':owner_k,**(meta_over or {})}
    meta={k:v for k,v in meta.items() if v is not ...}
    (folder/'set.json').write_text(json.dumps({'meta':meta,'queries':[
        {'claim_id':q.claim_id,'level':q.level,'text':q.text,'status':q.status,'record_sha256':q.record_sha256} for q in queries]},
        ensure_ascii=False),encoding='utf-8')
    if owner:
        sample=owner_sample(queries,owner_k if owner_count is None else owner_count,owner_seed,{r.claim_id:r.category for r in frame})
        write_owner_file(folder/'owner-check.json',sample,snapshot_hash(manifest(queries,meta)),{})
        data=json.loads((folder/'owner-check.json').read_text(encoding='utf-8'))
        for item in data['items']:
            item['verdict']='yes'
        (folder/'owner-check.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    return meta


def _write_set(folder,repo,story_id,owner=True,tweak=None,**kw):
    """A set over the story's sampling frame: three queries (same, syn, desc) per record, as the generator would write
    it; tweak(queries) may change the queries before the snapshot and the owner file are computed."""
    from memory_bench.extract import extract_story
    from memory_bench.paraphrase import FRAME_PARAMS,sampling_frame,story_names
    scenes,_=extract_story(repo,story_id,None)
    frame=sampling_frame(scenes,FRAME_PARAMS)
    assert frame,'the synthetic story must give the frame at least one record'
    queries=level_queries(frame,story_names(scenes))
    if tweak:
        queries=tweak(queries)
    write_para(folder,scenes,story_id,queries,owner=owner,**kw)
    return scenes,frame,queries


def _ok(queries,level):
    return sum(1 for q in queries if q.level==level and q.status=='ok')


def _para_args(repo,folder,*extra):
    return ['--data',str(repo.root),'--synthetic','','--paraphrases',str(folder),*extra]


def test_paraphrases_bm25_only_section(synthetic_repo,para_dir):
    repo,story_id,_=synthetic_repo
    _,frame,queries=_write_set(para_dir,repo,story_id)
    report,error=_report(_para_args(repo,para_dir))
    assert error is None and 'vector' not in report
    section=report['paraphrases']
    assert set(section['levels'])=={'same','syn','desc'} and section['owner']['no']==0 and section['snapshot']
    ok=sum(1 for q in queries if q.status=='ok')
    assert section['meta']['owner_k']==20 and section['meta']['owner_items']==min(20,ok)==section['owner']['yes']
    cell=section['levels']['same']['bm25']
    assert cell['n']==_ok(queries,'same') and cell['n']+cell['rejected']==len(frame)
    assert section['levels']['syn']['bm25']['n']==len(frame) and set(cell['in_plan']['in_context'])=={'0.75','0.5','0.35'}
    assert 'sign_vs_bm25' not in cell


def test_report_without_paraphrases_has_no_section(synthetic_repo):
    repo,_,_=synthetic_repo
    report,error=_report(['--data',str(repo.root),'--synthetic',''])
    assert error is None and 'paraphrases' not in report


def test_cli_refuses_without_owner_check(synthetic_repo,para_dir,monkeypatch):
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    _write_set(para_dir,repo,story_id,owner=False)
    assert _report(_para_args(repo,para_dir,'--vector-models','e5-base'))==(None,'owner_check_missing') and built==[]
    _write_set(para_dir,repo,story_id)
    path=para_dir/'set.json'  # the set changes after the owner looked at it
    path.write_text(path.read_text(encoding='utf-8').replace('Згадка:','Згадка інша:',1),encoding='utf-8')
    assert _report(_para_args(repo,para_dir,'--vector-models','e5-base'))==(None,'owner_check_stale') and built==[]


def test_cli_exit_code_is_the_refusal_code(synthetic_repo,para_dir):
    repo,story_id,_=synthetic_repo
    _write_set(para_dir,repo,story_id,owner=False)
    out=run_cli(_para_args(repo,para_dir))
    assert out.returncode==2 and out.stderr.strip()=='owner_check_missing' and out.stdout==''


def test_cli_refuses_set_of_changed_story(synthetic_repo,para_dir,monkeypatch):
    import dataclasses
    from memory_bench.paraphrase import _sha
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    # the set claims it was generated from another text of the first record; the owner file is valid for this set
    _write_set(para_dir,repo,story_id,tweak=lambda qs:[dataclasses.replace(qs[0],record_sha256=_sha('Інший текст запису')),*qs[1:]])
    assert _report(_para_args(repo,para_dir,'--vector-models','e5-base'))==(None,'paraphrase_set_stale') and built==[]
    _write_set(para_dir,repo,story_id)  # a fresh set for the same story passes
    report,error=_report(_para_args(repo,para_dir))
    assert error is None and 'paraphrases' in report


def test_cli_refuses_set_with_missing_claim(synthetic_repo,para_dir,monkeypatch):
    import dataclasses
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    _write_set(para_dir,repo,story_id,tweak=lambda qs:[dataclasses.replace(qs[0],claim_id='gone'),*qs[1:]])
    assert _report(_para_args(repo,para_dir,'--vector-models','e5-base'))==(None,'paraphrase_set_stale') and built==[]


def test_cli_paraphrases_inside_repo_and_invalid_set(synthetic_repo,para_dir):
    repo,_,_=synthetic_repo
    assert _report(_para_args(repo,ROOT/'docs'))==(None,'inside_repo')
    assert _report(_para_args(repo,para_dir))==(None,'paraphrase_set_invalid')  # no set.json
    (para_dir/'set.json').write_text('{"meta": 1}',encoding='utf-8')
    assert _report(_para_args(repo,para_dir))==(None,'paraphrase_set_invalid')


def test_paraphrases_report_has_no_texts(synthetic_repo,para_dir):
    repo,story_id,_=synthetic_repo
    scenes,frame,queries=_write_set(para_dir,repo,story_id)
    report,error=_report(_para_args(repo,para_dir))
    assert error is None
    dumped=json.dumps(report['paraphrases'],ensure_ascii=False)
    secrets={q.text for q in queries}|{r.text for s in scenes for r in s.records}|{s.plan_text for s in scenes}|set(SECRETS)
    assert len(secrets)>10
    for text in secrets:
        assert text and text not in dumped
    for r in frame:
        assert r.claim_id not in dumped
    assert story_id not in dumped


def test_paraphrases_with_vector_models(synthetic_repo,para_dir,monkeypatch,cache_dir):
    pytest.importorskip('numpy')
    repo,story_id,_=synthetic_repo;built=[]
    _patch_factory(monkeypatch,built)
    _write_set(para_dir,repo,story_id)
    report,error=_report(_vec_args(repo,cache_dir,'--vector-models','e5-base','--paraphrases',str(para_dir)))
    assert error is None and built==['e5-base']
    cell=report['paraphrases']['levels']['syn']
    assert set(cell)=={'bm25','vec[e5-base]','hybrid[e5-base]'}
    assert set(cell['vec[e5-base]']['sign_vs_bm25'])=={'standalone','in_plan'}
    assert set(cell['vec[e5-base]']['sign_vs_bm25_raw'])=={'standalone','in_plan'}
    assert set(cell['hybrid[e5-base]']['sign_in_context_vs_bm25'])=={'0.75','0.5','0.35'}


def _memory_story(monkeypatch,n=12):
    """An in-memory story of n records, facts and threads (unscoped states go to a layer and leave the frame); no
    database: extract_story of the bench is replaced."""
    from memory_bench.paraphrase import FRAME_PARAMS,sampling_frame,story_names
    from tests.retrieval_bench.helpers import rec,scene
    scenes=[scene([rec(f'r{i:02d}',('facts','open_threads')[i%2],f'Окремий запис {i} про маяк')
                   for i in range(n)])]
    monkeypatch.setattr(_bench(),'extract_story',lambda *a,**k:(scenes,{}))
    frame=sampling_frame(scenes,FRAME_PARAMS)
    return scenes,frame,level_queries(frame,story_names(scenes))


def _load(para_dir,story_id='story',protagonist=None):
    import types
    args=types.SimpleNamespace(paraphrases=str(para_dir),protagonist=protagonist)
    return _bench().load_paraphrases(args,None,types.SimpleNamespace(id=story_id))


def test_paraphrases_owner_k_must_be_20(para_dir,monkeypatch):
    """The spec fixes 20 owner items: a set generated with another owner_k is refused (12 records give 36 ok queries)."""
    scenes,frame,queries=_memory_story(monkeypatch)
    assert sum(q.status=='ok' for q in queries)==36
    write_para(para_dir,scenes,'story',queries,owner_k=10)
    assert _load(para_dir)==(None,'paraphrase_set_invalid')
    write_para(para_dir,scenes,'story',queries,owner_k=0)
    assert _load(para_dir)==(None,'paraphrase_set_invalid')
    write_para(para_dir,scenes,'story',queries,meta_over={'owner_k':...},owner_count=20)  # no owner_k: the default 20
    loaded,error=_load(para_dir)
    assert error is None and loaded['owner']=={'yes':20,'no':0,'invalid':0} and loaded['owner_items']==20
    write_para(para_dir,scenes,'story',queries,owner_count=10)  # meta says 20, the file holds 10
    assert _load(para_dir)==(None,'owner_check_missing')
    write_para(para_dir,scenes,'story',queries,owner_k=True,owner_count=20)
    assert _load(para_dir)==(None,'paraphrase_set_invalid')


def test_paraphrases_small_set_expects_all_ok_queries(para_dir,monkeypatch):
    scenes,frame,queries=_memory_story(monkeypatch,n=4)
    write_para(para_dir,scenes,'story',queries)
    loaded,error=_load(para_dir)
    assert error is None and loaded['owner_items']==12 and loaded['owner']['yes']==12


@pytest.mark.parametrize('field,value',[('level','para'),('status','maybe'),('status',None)])
def test_paraphrases_unknown_level_or_status_is_invalid(para_dir,monkeypatch,field,value):
    import dataclasses
    scenes,frame,queries=_memory_story(monkeypatch)
    write_para(para_dir,scenes,'story',[dataclasses.replace(queries[0],**{field:value}),*queries[1:]])
    assert _load(para_dir)==(None,'paraphrase_set_invalid')


def test_paraphrases_level_is_recomputed_at_eval(para_dir,monkeypatch):
    """An ok 'syn' query that shares stems with its record (or an ok 'same' that does not) makes the set stale."""
    import dataclasses
    scenes,frame,queries=_memory_story(monkeypatch)
    syn=next(i for i,q in enumerate(queries) if q.level=='syn')
    write_para(para_dir,scenes,'story',[*queries[:syn],dataclasses.replace(queries[syn],text=frame[0].text),*queries[syn+1:]])
    assert _load(para_dir)==(None,'paraphrase_set_stale')
    same=next(i for i,q in enumerate(queries) if q.level=='same')
    write_para(para_dir,scenes,'story',[*queries[:same],dataclasses.replace(queries[same],text='Жовтий човник'),*queries[same+1:]])
    assert _load(para_dir)==(None,'paraphrase_set_stale')
    rejected=[dataclasses.replace(q,text=frame[0].text,status='rejected') if q.level=='syn' and q.claim_id=='r00' else q
              for q in queries]  # a rejected query is not rechecked
    write_para(para_dir,scenes,'story',rejected)
    assert _load(para_dir)[1] is None


def test_paraphrases_story_and_protagonist_are_compared(para_dir,monkeypatch):
    scenes,frame,queries=_memory_story(monkeypatch)
    write_para(para_dir,scenes,'story',queries)
    assert _load(para_dir)[1] is None
    assert _load(para_dir,story_id='other')==(None,'paraphrase_set_stale')
    write_para(para_dir,scenes,'story',queries,meta_over={'protagonist':'c2'})
    assert _load(para_dir)==(None,'paraphrase_set_stale')
    write_para(para_dir,scenes,'story',queries,meta_over={'protagonist':...})
    assert _load(para_dir)==(None,'paraphrase_set_stale')


def test_paraphrases_owner_file_must_hold_the_recomputed_sample(para_dir,monkeypatch):
    """The eval recomputes owner_sample(queries, 20, meta.seed, categories) and compares it with the owner file."""
    scenes,frame,queries=_memory_story(monkeypatch)
    write_para(para_dir,scenes,'story',queries,owner_seed=1)  # 20 valid items, but not the sample of seed 0
    assert _load(para_dir)==(None,'owner_check_stale')
    write_para(para_dir,scenes,'story',queries,meta_over={'seed':'0'})
    assert _load(para_dir)==(None,'paraphrase_set_invalid')
