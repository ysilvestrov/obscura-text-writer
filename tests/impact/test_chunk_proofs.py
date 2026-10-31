import json
import pytest
from storygen.impact.chunking import plan_chunks
from storygen.impact.chunk_validation import validate_part,validate_manifest
from tests.impact.test_chunking import large_plan


def response(task,**updates):
    return dict(covered_ids=task['coverage'],summary='Перевірено частину.',verdict='no_impact',findings=[],evidence=[],uncertainty=None,**updates)


def test_missing_or_uncertain_proof(tmp_path):
    repo,plan=large_plan(tmp_path);m=plan_chunks(repo,plan)
    task=next(t for t in m.tasks if t['phase']=='reduce_check')
    with pytest.raises(ValueError):validate_part(response(task),m,task,{})
    results={id:dict(covered_ids=[],summary='Бракує даних',verdict='uncertain',findings=[],evidence=[],uncertainty='Пропуск') for id in task['dependencies']}
    with pytest.raises(ValueError,match='Невизначеність'):validate_part(response(task),m,task,results)


def test_quotes_outside_delivered_span_rejected(tmp_path):
    repo,plan=large_plan(tmp_path);m=plan_chunks(repo,plan)
    task=next(t for t in m.tasks if t['phase']=='delta')
    unit=m.units[task['units'][0]]
    bad=response(task);bad['evidence']=[dict(source_id=unit['source_id'],quote='НЕІСНУЮЧИЙ ДОКАЗ')]
    with pytest.raises(ValueError,match='цитат'):validate_part(bad,m,task,{})
    bad=response(task);bad['covered_ids']=[]
    with pytest.raises(ValueError,match='охоп'):validate_part(bad,m,task,{})


def test_manifest_integrity_and_complete_intervals(tmp_path):
    repo,plan=large_plan(tmp_path);m=plan_chunks(repo,plan)
    validate_manifest(m)
    broken=m.model_copy(deep=True);broken.tasks.pop(0)
    with pytest.raises(ValueError):validate_manifest(broken)
    broken=m.model_copy(deep=True);next(iter(broken.units.values()))['core_start']=10
    with pytest.raises(ValueError):validate_manifest(broken)


def test_synthesis_can_find_cross_part_issue_from_exact_child_quotes(tmp_path):
    repo,plan=large_plan(tmp_path);m=plan_chunks(repo,plan)
    task=next(t for t in m.tasks if t['phase']=='reduce_check')
    target=plan.targets[0];change=next(c for c in target.changes if c.changed)
    quote=target.text[:16];source_quote=change.new_text[:16]
    children={id:dict(covered_ids=[],summary='Цільова цитата: '+quote,verdict='no_impact',findings=[],evidence=[dict(source_id=change.id+':new',quote=source_quote)],uncertainty=None) for id in task['dependencies']}
    raw=response(task);raw.update(verdict='changes_required',findings=[dict(target_quote=quote,change_ids=[change.id],explanation='Суперечність видно при зіставленні частин.',evidence=[dict(source_id=change.id+':new',quote=source_quote)])])
    assert validate_part(raw,m,task,children).verdict=='changes_required'


def test_synthesized_memory_quote_must_exist_in_original_journal(tmp_path):
    from storygen.impact.chunk_validation import combined_result
    repo,plan=large_plan(tmp_path);m=plan_chunks(repo,plan);target=plan.targets[0].model_copy(update={'memory_text':'Справжній факт.'})
    roots=m.roots[target.version_id];roots['memory']='memory-root'
    text=dict(covered_ids=[],summary='Перевірено.',verdict='no_impact',findings=[],evidence=[],uncertainty=None)
    change=next(c for c in target.changes if c.changed)
    memory={**text,'verdict':'changes_required','findings':[dict(target_quote='Вигадана цитата',change_ids=[change.id],explanation='Потребує зміни.',evidence=[dict(source_id=change.id+':new',quote=change.new_text[:10])])]}
    with pytest.raises(ValueError,match='цитата цільового'):
        combined_result(m,target,{roots['text']:text,'memory-root':memory})
