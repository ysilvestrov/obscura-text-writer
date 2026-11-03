import pytest
from storygen.generation.rewrite_review import rewrite_preview,selection_preview,classify_location

@pytest.mark.parametrize('start,end,expected',[(1,3,'inside'),(6,8,'outside'),(1,6,'cross_boundary'),(0,0,'cross_boundary'),(5,5,'cross_boundary'),(2,2,'inside'),(8,8,'outside')])
def test_location_is_geometric_not_a_compliance_claim(start,end,expected):
    assert classify_location(start,end,[dict(id='x',start=0,end=5)])['location']==expected


def test_rewrite_preview_uses_groups_and_empty_selection(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    p=rewrite_preview(repo,scene.id,attempt.id)
    assert p['default_selected_indices']==[] and p['can_apply']
    assert p['groups'] and all('location' in e for e in p['edits'])
    assembled=selection_preview(repo,scene.id,attempt.id,[],p['expected_revision'],p['proposal_fingerprint'],notes.revision)
    assert assembled['text']==repo.read_text(source.id)
    assert p['comments']['general']==notes.general
