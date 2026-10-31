"""Seeded common TP panel, all-model visibility and complete secondary review."""
import pytest


def rows():
    return [dict(case=f'case-{i}',draw=1,config=model,tp_ids=[f'fact-{i}'] if model=='L1' or i%2==0 else [],
                 pending=False,outcome='TP',measurement='primary')
            for i in range(10) for model in ['L1','L2']]


def test_shared_panel_meets_each_model_quota_and_includes_misses():
    from .review import shared_tp_panel
    values=rows();panel=shared_tp_panel(values,seed=17)
    assert panel==shared_tp_panel(list(reversed(values)),seed=17)
    assert panel['quotas']=={'L1':2,'L2':1}
    assert all(panel['covered'][m]>=n for m,n in panel['quotas'].items())
    for unit in panel['units']:
        assert {r['config'] for r in unit['responses']}=={'L1','L2'}
    assert len(panel['units'])<=3


def test_panel_rejects_pending_duplicate_or_secondary_measurements():
    from .review import shared_tp_panel
    for changed in [dict(pending=True),dict(measurement='secondary')]:
        values=rows();values[0].update(changed)
        with pytest.raises(ValueError):shared_tp_panel(values,seed=17)
    with pytest.raises(ValueError):shared_tp_panel(rows()+[rows()[0]],seed=17)


def test_blind_export_has_all_responses_without_identity_usage_or_owner_answers():
    from .review import blind_export,shared_tp_panel
    values=rows()
    replies={(r['case'],r['draw'],r['config']):dict(text='Відповідь',status='valid',provider_model=r['config'],usage={'model':r['config']}) for r in values}
    panel=shared_tp_panel(values,seed=17)
    form,key=blind_export(panel,replies,seed=21)
    assert set(key.values())=={'L1','L2'}
    assert all('config' not in r and r['owner_adjudication'] is None
               for unit in form['units'] for r in unit['responses'])
    assert 'provider_model' not in str(form) and 'usage' not in str(form) and 'tp_ids' not in str(form)
    assert 'seed' not in form


def test_secondary_form_includes_every_candidate_even_executor_fn():
    from .review import secondary_form
    values=[dict(case='x',draw=1,config='L1',response=dict(status='invalid',text='original',secondary_eligible=True),
                 executor_adjudication={'matches':{}}),
            dict(case='y',draw=1,config='L2',response=dict(status='invalid',text='bad',secondary_eligible=False))]
    form=secondary_form(values)
    assert len(form)==1 and form[0]['response']['text']=='original'
    assert form[0]['owner_adjudication'] is None


def test_executor_form_is_blind_and_does_not_drop_invalid_slots():
    from .review import executor_form
    from .test_round2 import case
    c=case()
    records=[dict(case=c['id'],draw=1,config=m,response=dict(status=status,text='original'))
             for m,status in [('L1','invalid'),('C1','valid')]]
    form,key=executor_form(records,{c['id']:c},seed=17)
    assert len(form['units'])==1 and len(form['units'][0]['responses'])==2
    assert {r['status'] for r in form['units'][0]['responses']}=={'invalid','valid'}
    assert 'executor_adjudication' in form['units'][0]['responses'][0]
    assert set(key.values())=={'L1','C1'}


def test_blind_form_decisions_are_applied_without_guessing_missing_labels():
    from .review import executor_form,adjudicate_form
    from .test_round2 import case,prepared,response
    c=case();res=response(prepared())
    records=[dict(case=c['id'],draw=1,config='L1',response=res)]
    form,key=executor_form(records,{c['id']:c},seed=17)
    with pytest.raises(ValueError,match='adjudication'):adjudicate_form(form,key,records,{c['id']:c})
    form['units'][0]['responses'][0]['executor_adjudication']=dict(content_refusal=False,matches={},question_ok=False)
    primary,secondary=adjudicate_form(form,key,records,{c['id']:c})
    assert primary[0]['outcome']=='FN' and primary[0]['config']=='L1'
    assert secondary==[]
