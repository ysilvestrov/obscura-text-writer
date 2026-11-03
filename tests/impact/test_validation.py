import pytest
from pydantic import ValidationError
from storygen.impact.models import DeltaReport,CheckReport
from storygen.impact.validation import validate_delta,validate_check
from storygen.impact.planning import capture_target
from tests.impact.test_planning import seeded
from storygen.generation.dependencies import save_manual_prose


def target(root):
    repo,story,first,second,ref=seeded(root)
    save_manual_prose(repo,first.id,'Марія не знає про лист.',repo.get_scene(first.id).revision)
    return capture_target(repo.context_view(story.id),ref.id)


def test_coverage_and_exact_evidence(tmp_path):
    t=target(tmp_path);ids=[c.id for c in t.changes if c.changed]
    d=dict(covered_change_ids=ids,items=[],uncertainty=None)
    assert validate_delta(d,t).covered_change_ids==ids
    with pytest.raises(ValueError):validate_delta({**d,'covered_change_ids':[]},t)
    change=next(c for c in t.changes if c.changed)
    item=dict(change_ids=[change.id],category='fact',before='знає',after='не знає',explanation='Змінилися знання.',evidence=[dict(source_id=change.id+':new',quote='НЕІСНУЮЧА ЦИТАТА')])
    with pytest.raises(ValueError,match='цитат'):validate_delta({**d,'items':[item]},t)


def test_no_impact_requires_complete_material_coverage(tmp_path):
    t=target(tmp_path);ids=[c.id for c in t.changes if c.changed]
    raw=dict(materials=[dict(version_id=t.version_id,verdict='no_impact',covered_change_ids=ids,explanation='Події узгоджуються.',findings=[])],memory_semantic_impact='unchecked',memory_explanation='Окреме оновлення.')
    assert validate_check(raw,t).materials[0].verdict=='no_impact'
    raw['materials'][0]['covered_change_ids']=[]
    with pytest.raises(ValueError):validate_check(raw,t)


def test_ambiguous_json_is_not_silently_accepted():
    from storygen.impact.validation import decode_response
    with pytest.raises(ValueError):decode_response('{"materials":[],"materials":[]}')
    with pytest.raises(ValueError):decode_response('{"value":NaN}')
