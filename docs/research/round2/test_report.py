"""Owner-approved L5 sanity check uses three separate metrics, no weighted score."""
import pytest


def row(fp=5,miss=8,valid=140):
    return dict(total=144,clean_denominator=60,issue_denominator=84,fp=fp,miss=miss,valid=valid)


def test_l5_dominance_requires_no_worse_on_all_three_axes():
    from .report import l5_dominators
    candidates={k:row() for k in ['L1','L2','L3','L4']}
    candidates['L1']=row(fp=4)
    candidates['L2']=row(fp=3,miss=9)
    assert l5_dominators(row(),candidates)==['L1']
    candidates['L1']=row()
    assert l5_dominators(row(),candidates)==[]  # Ties/tradeoffs do not establish a winner.


def test_l5_comparison_requires_all_four_locals_and_equal_complete_denominators():
    from .report import l5_dominators
    with pytest.raises(ValueError):l5_dominators(row(),{'L1':row()})
    candidates={k:row() for k in ['L1','L2','L3','L4']}
    candidates['L1']['total']=143
    with pytest.raises(ValueError):l5_dominators(row(),candidates)


def test_flip_tracks_model_verdict_not_tp_labels():
    from .report import flip_rate,model_verdict
    a=dict(status='valid',parsed={'concerns':[]})
    b=dict(status='valid',parsed={'concerns':[{'kind':'issue'}]})
    assert model_verdict(a)=='clean' and model_verdict(b)=='issue'
    rows=[dict(case='x',draw=i,verdict=v) for i,v in enumerate(['clean','issue','clean'],1)]
    assert flip_rate(rows)==dict(changed=1,cases=1,rate=1.0)
    with pytest.raises(ValueError):flip_rate(rows[:2])


def test_primary_summary_has_each_draw_context_and_baselines():
    from .report import primary_summary
    from .scoring import baseline
    from pathlib import Path
    import json
    cases=json.loads((Path(__file__).parent/'holdout.json').read_text(encoding='utf-8'))
    records=[dict(baseline(c['gold'],'always-clean'),case=c['id'],config='L1',draw=d,context=c['context'],
                  verdict='clean') for d in [1,2,3] for c in cases]
    summary=primary_summary(records,cases)
    m=summary['models']['L1']
    assert m['aggregate']['miss']==84 and m['thresholds_passed'] is False
    assert set(m['draws'])=={'1','2','3'} and m['contexts']['adult']['total']==72
    assert summary['baselines']['K1']['thresholds_passed'] is False
    assert summary['baselines']['K2']['thresholds_passed'] is False
    assert m['flip']['changed']==0
