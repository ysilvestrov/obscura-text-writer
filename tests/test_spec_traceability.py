import json
from pathlib import Path

import pytest

from scripts.check_docs import check


def fixture(root):
    (root/'docs/verification').mkdir(parents=True)
    (root/'tests').mkdir()
    (root/'SPEC.MD').write_text('### Requirement: DEMO-001 — Контракт\n\n#### Scenario: DEMO-001-S01 — Приклад\n- GIVEN дані\n- WHEN дія\n- THEN результат\n',encoding='utf-8')
    (root/'tests/test_demo.py').write_text('def test_demo():\n    assert True\n',encoding='utf-8')
    matrix={'version':1,'scenarios':[{'id':'DEMO-001-S01','requirement':'DEMO-001','tests':['tests/test_demo.py::test_demo'],'scope':'Конкретний результат.'}]}
    write_matrix(root,matrix)
    return matrix


def write_matrix(root,matrix):
    (root/'docs/verification/traceability.json').write_text(json.dumps(matrix,ensure_ascii=False),encoding='utf-8')


def test_valid_specific_mapping(tmp_path):
    fixture(tmp_path)
    assert check(tmp_path,documents=['SPEC.MD'])==[]


@pytest.mark.parametrize('fault',['missing','extra','duplicate','unknown_test','wildcard','wrong_requirement','escape','empty_scope'])
@pytest.mark.req('DOCS-TRACE')
def test_invalid_mapping_is_error(tmp_path,fault):
    matrix=fixture(tmp_path);row=matrix['scenarios'][0]
    if fault=='missing':matrix['scenarios']=[]
    if fault=='extra':matrix['scenarios'].append({**row,'id':'DEMO-001-S02'})
    if fault=='duplicate':matrix['scenarios'].append(row.copy())
    if fault=='unknown_test':row['tests']=['tests/test_demo.py::test_absent']
    if fault=='wildcard':row['tests']=['tests/test_demo.py::*']
    if fault=='wrong_requirement':row['requirement']='OTHER-001'
    if fault=='escape':row['tests']=['../outside.py::test_demo']
    if fault=='empty_scope':row['scope']=' '
    write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])


@pytest.mark.parametrize('fault',['duplicate_id','missing_id','no_scenarios'])
def test_invalid_spec_structure(tmp_path,fault):
    fixture(tmp_path);path=tmp_path/'SPEC.MD';text=path.read_text(encoding='utf-8')
    if fault=='duplicate_id':text+='\n#### Scenario: DEMO-001-S01 — Інший\n'
    if fault=='missing_id':text=text.replace('DEMO-001-S01 — ','')
    if fault=='no_scenarios':text=text.split('#### Scenario:')[0]
    path.write_text(text,encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD'])


@pytest.mark.req('DOCS-TRACE')
def test_manual_mapping_requires_procedure_and_reason(tmp_path):
    matrix=fixture(tmp_path);row=matrix['scenarios'][0];row['tests']=[]
    row['manual']={'procedure':'docs/manual.md#check','reason':'Потрібне авторське судження.'}
    (tmp_path/'docs/manual.md').write_text('# Check\n\nПрочитайте текст і запишіть результат. Сам опис не є виконанням.\n',encoding='utf-8')
    write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])==[]
    row['manual']['reason']='';write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])


@pytest.mark.parametrize('procedure',['//example.invalid/procedure','#','SPEC.MD','https://example.invalid/#check'])
def test_manual_procedure_must_name_local_document_and_anchor(tmp_path,procedure):
    matrix=fixture(tmp_path);row=matrix['scenarios'][0];row['tests']=[]
    row['manual']={'procedure':procedure,'reason':'Потрібне людське рішення.'}
    write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])


def test_manual_procedure_cannot_use_non_document_with_fake_anchor(tmp_path):
    matrix=fixture(tmp_path);row=matrix['scenarios'][0];row['tests']=[]
    row['manual']={'procedure':'tests/test_demo.py#invented','reason':'Авторське судження.'}
    write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])


@pytest.mark.parametrize('source',[
    '__test__=False\ndef test_demo(): pass\n',
    'def test_demo(): pass\ntest_demo.__test__=False\n',
    'import pytest\n@pytest.fixture\ndef test_demo(): pass\n'])
def test_explicitly_noncollected_function_is_not_a_test_binding(tmp_path,source):
    fixture(tmp_path);(tmp_path/'tests/test_demo.py').write_text(source,encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD'])


def test_wrong_requirement_type_is_reported_without_crashing(tmp_path):
    matrix=fixture(tmp_path);matrix['scenarios'][0]['requirement']=[];write_matrix(tmp_path,matrix)
    assert check(tmp_path,documents=['SPEC.MD'])


@pytest.mark.parametrize('target',['missing.md','SPEC.MD#absent','../outside.md'])
def test_broken_document_links(tmp_path,target):
    fixture(tmp_path)
    (tmp_path/'README.md').write_text(f'[Перехід]({target})',encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD','README.md'])


def test_markers_are_specific_and_known(tmp_path):
    fixture(tmp_path);path=tmp_path/'tests/test_demo.py'
    path.write_text('import pytest\n@pytest.mark.req("DEMO-001")\ndef test_demo():\n    pass\n',encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD'])==[]
    path.write_text(path.read_text().replace('DEMO-001','UNKNOWN-001'),encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD'])


def test_module_marker_does_not_count_as_coverage(tmp_path):
    fixture(tmp_path)
    (tmp_path/'tests/test_demo.py').write_text('import pytest\npytestmark=pytest.mark.req("DEMO-001")\ndef test_demo(): pass\n',encoding='utf-8')
    assert check(tmp_path,documents=['SPEC.MD'])


def test_async_class_parameterized_tests_and_fenced_examples(tmp_path):
    matrix=fixture(tmp_path)
    matrix['scenarios'][0]['tests']=['tests/test_demo.py::TestDemo::test_demo']
    write_matrix(tmp_path,matrix)
    (tmp_path/'tests/test_demo.py').write_text('import pytest\nclass TestDemo:\n    @pytest.mark.parametrize("value",[1,2])\n    @pytest.mark.req("DEMO-001")\n    async def test_demo(self,value): pass\n',encoding='utf-8')
    with (tmp_path/'SPEC.MD').open('a',encoding='utf-8') as out:out.write('\n```md\n### Requirement: not an ID\n[Fake](missing.md)\n```\n')
    assert check(tmp_path,documents=['SPEC.MD'])==[]


def test_repository_traceability():
    root=Path(__file__).resolve().parents[1]
    assert check(root)==[]


@pytest.mark.req('EDIT-001')
@pytest.mark.parametrize('field,limit',[('original',160),('replacement',240),('edits',80)])
def test_copyedit_numeric_boundaries(field,limit):
    from pydantic import ValidationError
    from storygen.copyediting import CopyEdits
    base=dict(fragment_id='f000001',original='слово',replacement='інше',category='grammar')
    def proposal(size):
        return {'edits':[base.copy() for _ in range(size)]} if field=='edits' else {'edits':[{**base,field:'а'*size}]}
    CopyEdits.model_validate(proposal(limit))
    with pytest.raises(ValidationError):CopyEdits.model_validate(proposal(limit+1))
