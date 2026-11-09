"""#44: author_lineage on manual saves and brief_link in the lineage walk."""
from storygen.domain import BriefLink
from storygen.generation.dependencies import save_manual_draft,save_manual_prose
from storygen.characters.acquaintance import lineage_brief,lineage_source,introduced_of
from tests.characters.test_acquaintance_history import setup,brief,with_brief_prose,run


def set_link(repo,version_id,brief_id,introduced):
    ref=repo.get_version(version_id)
    ref.brief_link=BriefLink(brief_version_id=brief_id,introduced=introduced,confirmed_at='2026-11-09T00:00:00Z')
    with repo.db.connection() as db:
        db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),version_id))


def edges(repo,version_id):
    with repo.db.connection() as db:
        return sorted(row[0] for row in db.execute('SELECT source_id FROM dependency_edges WHERE target_id=?',(version_id,)))


def test_manual_prose_records_previous_head_without_new_dependencies(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B'],['A','B']])
    b,edited=with_brief_prose(repo,story,s1,['B'])
    ref=save_manual_prose(repo,s1.id,'Нова проза.',repo.get_scene(s1.id).revision)
    assert ref.author_lineage.parent_version_id==edited.id
    assert edited.id not in ref.input_refs and edited.id not in ref.dependency_snapshot.refs
    assert edited.id not in edges(repo,ref.id)
    view=repo.context_view(story.id)
    assert lineage_brief(view,view.get_scene(s1.id)).id==b.id
    assert run(repo,story,1).known=={'B':1}


def test_manual_draft_records_previous_draft_head(tmp_path):
    repo,story,(s1,)=setup(tmp_path,casts=[['A','B']])
    first=save_manual_draft(repo,s1.id,'Чернетка 1.',repo.get_scene(s1.id).revision)
    assert first.author_lineage is None
    second=save_manual_draft(repo,s1.id,'Чернетка 2.',repo.get_scene(s1.id).revision)
    assert second.author_lineage.parent_version_id==first.id
    assert first.id not in second.input_refs and first.id not in edges(repo,second.id)


def test_author_lineage_must_stay_in_scene(tmp_path):
    import pytest
    from storygen.domain import AuthorLineage
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A'],['A']])
    other=repo.save_version(story.id,s2.id,'draft','Ч.',[])
    with pytest.raises(ValueError):
        repo.save_version(story.id,s1.id,'draft','Ч.',[],author_lineage=AuthorLineage(parent_version_id=other.id))


def test_link_wins_over_lineage_brief_and_is_inherited(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B','C'],['A']])
    b,edited=with_brief_prose(repo,story,s1,None)
    current=brief(repo,story,s1,None)
    set_link(repo,edited.id,current.id,['C'])
    view=repo.context_view(story.id)
    kind,ref=lineage_source(view,view.get_scene(s1.id))
    assert (kind,ref.id)==('link',edited.id)
    assert introduced_of(view,view.get_scene(s1.id))==['C']
    assert run(repo,story,1).known=={'C':1}
    save_manual_prose(repo,s1.id,'Правка автора.',repo.get_scene(s1.id).revision)
    assert run(repo,story,1).known=={'C':1}


def test_link_introduced_is_cut_to_current_cast(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B','C'],['A']])
    b,edited=with_brief_prose(repo,story,s1,None)
    set_link(repo,edited.id,b.id,['B','Z'])  # Z left the cast after the confirmation
    assert run(repo,story,1).known=={'B':1}


def test_without_link_behaviour_is_unchanged(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B'],['A']])
    from tests.characters.test_acquaintance_history import prose
    prose(repo,story,s1)
    assert run(repo,story,1).known=={'B':1}
