"""Owner panel import and final-report gates; executor labels stay provisional."""
from copy import deepcopy
import json
from pathlib import Path
import pytest


def sample():
    from .scoring import baseline
    from .review import shared_tp_panel,blind_export
    cases=json.loads((Path(__file__).parent/'holdout.json').read_text(encoding='utf-8'))
    by_id={c['id']:c for c in cases};rows=[];responses={}
    for label in ['L1','L2','L3','L4','L5','L6','C1','C2']:
        for c in cases:
            for draw in [1,2,3]:
                r=baseline(c['gold'],'always-clean' if label=='L5' else 'always-issue')
                rows.append(dict(r,case=c['id'],draw=draw,config=label,verdict='clean' if label=='L5' else 'issue'))
                concerns=[] if label=='L5' else [{'kind':'issue'} for _ in c['gold']['contradictions']]
                responses[(c['id'],draw,label)]=dict(status='valid',text='original',parsed={'concerns':concerns})
    panel=shared_tp_panel(rows,seed=17);form,key=blind_export(panel,responses,seed=19,cases=by_id)
    for unit in form['units']:
        for reply in unit['responses']:
            label=key[reply['model']];gold=by_id[unit['case']]['gold']
            reply['owner_adjudication']=dict(content_refusal=False,question_ok=False,
                matches={} if label=='L5' else {str(i):[f['id']] for i,f in enumerate(gold['contradictions'])})
    return cases,rows,responses,panel,form,key


def test_owner_panel_accepts_repeated_slots_and_keeps_executor_history():
    from .review import apply_owner_panel
    cases,rows,responses,panel,form,key=sample()
    updated,audit=apply_owner_panel(panel,form,key,rows,responses,{c['id']:c for c in cases})
    assert audit['completed'] and audit['decisions']
    assert all('executor_classification' in d and 'owner_adjudication' in d for d in audit['decisions'])
    assert len(updated)==len(rows)
    changed=deepcopy(form);changed['units'][0]['responses'][0]['owner_adjudication']=None
    with pytest.raises(ValueError):apply_owner_panel(panel,changed,key,rows,responses,{c['id']:c for c in cases})


def test_final_report_requires_all_eight_owner_panel_and_every_secondary():
    from .report import final_primary_summary,primary_summary
    from .review import apply_owner_panel
    cases,rows,responses,panel,form,key=sample()
    assert primary_summary(rows,cases)['provisional'] is True
    assert primary_summary(rows,cases)['model_conclusion_allowed'] is False
    updated,audit=apply_owner_panel(panel,form,key,rows,responses,{c['id']:c for c in cases})
    report=final_primary_summary(updated,cases,owner_review=audit,panel=panel,secondary=[])
    assert report['provisional'] is False
    with pytest.raises(ValueError):final_primary_summary(updated,cases,owner_review=dict(audit,completed=False),panel=panel,secondary=[])
    with pytest.raises(ValueError):final_primary_summary([r for r in updated if r['config']!='C2'],cases,owner_review=audit,panel=panel,secondary=[])
    bad=deepcopy(audit);bad['secondary_candidate_slots']=[['case',1,'L1']]
    with pytest.raises(ValueError,match='secondary'):final_primary_summary(updated,cases,owner_review=bad,panel=panel,secondary=[])
