import json

from memory_bench.metrics import aggregate, control_hits, scene_metrics
from memory_bench.strategies import STRATEGIES, Params, catalog_full, catalog_narrow
from tests.retrieval_bench.helpers import rec, rich_records, scene

P=Params(memory_budget_tokens=100000,measure='conservative',core_mode='upper')


def test_target_recall_counts_hits():
    s=scene(rich_records(),cast=('c2',),targets=('pres1','absent'))
    row=scene_metrics(s,STRATEGIES['structural'](s,P))
    assert (row['targets'],row['targets_hit'])==(2,1)
    agg=aggregate([row],[STRATEGIES['structural'](s,P)])
    assert agg['target_recall']==0.5 and agg['scenes_with_missed_target']==1 and agg['scene_count']==1


def test_aggregate_empty_story():
    agg=aggregate([],[])
    assert agg['scene_count']==0 and agg['target_recall'] is None and agg['chars'] is None


def test_aggregate_no_targets_gives_none_recall():
    s=scene(rich_records())
    assert aggregate([scene_metrics(s,STRATEGIES['full'](s,P))],[STRATEGIES['full'](s,P)])['target_recall'] is None


def test_catalog_full_matches_v3_layout_size():
    s=scene(rich_records())
    mutable=[{'claim_id':r.claim_id,'category':r.category,'text':r.text,'character_ids':list(r.character_ids)}
             for r in s.records if r.category in {'character_states','open_threads'}]
    immutable=[{'category':r.category,'text':r.text} for r in s.records if r.category not in {'character_states','open_threads'}]
    expected=json.dumps({'mutable':mutable,'immutable':immutable},ensure_ascii=False,separators=(',',':'))
    assert catalog_full(s).chars==len(expected)


def test_narrow_catalog_contains_targets_of_present_and_linked():
    s=scene(rich_records(),cast=('c1','c2'),targets=('core1','pres1','thr1'),prose='Остап шукав ключ')
    narrow=catalog_narrow(s,P)
    assert {'core1','pres1','thr1'}<=set(narrow.record_ids) and 'absent' not in narrow.record_ids


def test_narrow_catalog_fts_uses_prose():
    s=scene(rich_records(),cast=('c1',),prose='Ганна поїхала в місто, вовка бачили')
    assert 'thr_far' in catalog_narrow(s,P).record_ids


def test_narrow_catalog_smaller_than_full_on_rich_scene():
    s=scene(rich_records(),cast=('c1',))
    assert catalog_narrow(s,P).chars<catalog_full(s).chars


def test_control_hits_reasons_and_no_ids_in_output():
    s=scene(rich_records(),id='s3',cast=('c2',))
    sels={'s3':STRATEGIES['structural'](s,P)}
    out=control_hits([{'scene_id':'s3','claim_id':'pres1'},{'scene_id':'s3','claim_id':'absent_claim'},
                      {'scene_id':'s9','claim_id':'pres1'},{'scene_id':'s3','claim_id':'fact_far'}],{'s3':s},sels)
    assert out==[{'index':0,'hit':True,'reason':None},{'index':1,'hit':None,'reason':'missing_in_memory'},
                 {'index':2,'hit':None,'reason':'scene_skipped'},{'index':3,'hit':False,'reason':None}]


def test_jaccard_adjacent():
    atm=[rec(f'old{i}','character_states',f'Марія любить річ {i}',['c1'],1) for i in range(40)]
    p=Params(memory_budget_tokens=4000,measure='conservative',core_mode='lower',atmosphere_share=0.1)
    scenes=[scene(atm,id=f's{i}') for i in range(3)]
    sels=[STRATEGIES['structural'](s,p) for s in scenes]
    agg=aggregate([scene_metrics(s,x) for s,x in zip(scenes,sels)],sels)
    assert 0<=agg['atmosphere_jaccard_adjacent']<1 and agg['atmosphere_mean']>0
    same=aggregate([scene_metrics(scenes[0],sels[0])]*2,[sels[0]]*2)
    assert same['atmosphere_jaccard_adjacent']==1


def test_recall_fitting_excludes_overflow_scenes():
    ok=scene(rich_records(),cast=('c2',),targets=('pres1',),id='a')
    big=[rec(f'core{i}','character_states','Марія '+'дуже '*40,['c1']) for i in range(10)]
    bad=scene(big+rich_records(),cast=('c2',),targets=('pres1',),id='b')
    p=Params(memory_budget_tokens=300,measure='conservative',core_mode='upper')
    sels=[STRATEGIES['structural'](ok,P),STRATEGIES['structural'](bad,p)]
    agg=aggregate([scene_metrics(ok,sels[0]),scene_metrics(bad,sels[1])],sels)
    assert agg['target_recall']==0.5 and agg['target_recall_fitting']==1.0
