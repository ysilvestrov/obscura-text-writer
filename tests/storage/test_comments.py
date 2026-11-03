import pytest

from storygen.domain import StoryCreate,SceneCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_draft
from storygen.authoring.comments import CommentPayload,OriginSource,CommentOrigin,validate_comment_set,comment_fingerprint


def fixture(root):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Зорі'))
    scene=repo.create_scene(story.id,SceneCreate(title='Парк'))
    version=save_manual_draft(repo,scene.id,'😀 Лєра дивилася вгору.',scene.revision)
    return repo,story,repo.get_scene(scene.id),version


def payload(**changes):
    value={'general':'Скоротити вступ.','comments':[{'id':'note1','instruction':'Більше емоцій.',
        'anchor':{'start':2,'end':6,'source_quote':'Лєра','display_quote':'Лєра','state':'valid'}}]}
    value.update(changes)
    return CommentPayload.model_validate(value)


def save(repo,scene,version,notes,revision=0,text=None,format=None):
    return repo.save_draft_with_comments(scene.id,repo.read_text(version.id) if text is None else text,
        format or version.content_format,scene.revision,revision,notes,expected_source_version_id=version.id)


def test_notes_only_and_full_noop_preserve_text_revisions_and_dependents(tmp_path):
    repo,story,scene,version=fixture(tmp_path)
    dependent=repo.save_version(story.id,scene.id,'brief','{}',[version.id])
    original_story_revision=repo.get_story(story.id).revision
    first=save(repo,scene,version,payload())
    assert first['version'].id==version.id
    assert first['scene'].revision==scene.revision
    assert first['comment_set'].revision==1
    same=save(repo,scene,version,payload(),1)
    assert same['comment_set'].id==first['comment_set'].id
    assert comment_fingerprint(same['comment_set'],version)==comment_fingerprint(first['comment_set'],version)
    updated=save(repo,scene,version,payload(general='Скоротити ще.'),1)
    assert updated['comment_set'].revision==2
    assert repo.get_scene(scene.id).heads['draft']==version.id
    assert repo.get_story(story.id).revision==original_story_revision
    assert not repo.get_version(dependent.id).stale


def test_text_and_comments_save_is_one_cas_publication(tmp_path):
    repo,_,scene,version=fixture(tmp_path)
    first=save(repo,scene,version,payload())
    updated=save(repo,scene,version,payload(),1,text=repo.read_text(version.id)+' Новий рядок.')
    assert updated['version'].id!=version.id
    assert updated['scene'].revision==scene.revision+1
    assert updated['comment_set'].source_version_id==updated['version'].id
    assert first['comment_set'].source_version_id==version.id
    with pytest.raises(RevisionConflict):save(repo,scene,version,payload(),1,text='Не застосувати.')
    assert repo.get_scene(scene.id).heads['draft']==updated['version'].id


@pytest.mark.parametrize('ranges,allowed',[([(0,3),(3,5)],True), ([(0,3),(2,5)],False), ([(0,5),(1,3)],False)])
def test_half_open_ranges_allow_adjacent_but_not_overlapping(ranges,allowed):
    text='абвгд'
    notes=CommentPayload.model_validate({'comments':[{'id':str(i),'instruction':'Вказівка','anchor':{
        'start':start,'end':end,'source_quote':text[start:end],'display_quote':text[start:end],'state':'valid'}} for i,(start,end) in enumerate(ranges)]})
    if allowed:validate_comment_set(text,'plain',notes)
    else:
        with pytest.raises(ValueError):validate_comment_set(text,'plain',notes)


def test_exact_quote_and_whole_document_markdown_mapping():
    text='А **зорі** та &amp; 😀.'
    start=text.index('зорі');end=text.index(' та')+3
    notes=CommentPayload.model_validate({'comments':[{'id':'a','instruction':'Переписати','anchor':{
        'start':start,'end':end,'source_quote':text[start:end],'display_quote':'зорі та','state':'valid'}}]})
    validate_comment_set(text,'markdown',notes)
    bad=notes.model_copy(deep=True);bad.comments[0].anchor.source_quote='інша цитата'
    with pytest.raises(ValueError):validate_comment_set(text,'markdown',bad)


def test_unpublished_origin_retains_source_and_survives_reopen(tmp_path):
    repo,_,scene,version=fixture(tmp_path)
    notes=payload()
    notes.comments[0].anchor.state='needs_review'
    notes.comments[0].anchor.reason='Фрагмент змінено.'
    notes.comments[0].anchor.origin_source=OriginSource(text='😀 Лєра була тут.',content_format='plain')
    result=save(repo,scene,version,notes,text='Лєра вже пішла.')
    stored=Repository(tmp_path).get_comment_set(scene.id)
    origin=stored.comments[0].anchor.origin
    assert stored.comments[0].anchor.state=='needs_review'
    assert 'origin_source' not in stored.model_dump_json()
    assert repo.files.read(origin.relative_path,origin.sha256).decode()=='😀 Лєра була тут.'
    assert stored.source_version_id==result['version'].id


def test_comment_insert_failure_rolls_back_text_and_notes(tmp_path,monkeypatch):
    repo,_,scene,version=fixture(tmp_path)
    before=save(repo,scene,version,payload())
    from storygen.storage import comment_store
    def fail(*args):raise OSError('disk failure')
    monkeypatch.setattr(comment_store,'_insert_comment_set',fail)
    with pytest.raises(OSError):save(repo,scene,version,payload(),1,text=repo.read_text(version.id)+' Далі.')
    assert repo.get_scene(scene.id).heads['draft']==version.id
    assert repo.get_comment_set(scene.id).id==before['comment_set'].id


def test_origin_from_other_scene_is_rejected_without_publication(tmp_path):
    repo,story,scene,version=fixture(tmp_path)
    other=repo.create_scene(story.id,SceneCreate(title='Інша'))
    foreign=save_manual_draft(repo,other.id,repo.read_text(version.id),other.revision)
    scene=repo.get_scene(scene.id)
    notes=payload();notes.comments[0].anchor.state='needs_review'
    notes.comments[0].anchor.origin=CommentOrigin(version_id=foreign.id,sha256=foreign.sha256,content_format=foreign.content_format)
    with pytest.raises(ValueError):save(repo,scene,version,notes,text='Не публікувати.')
    assert repo.get_scene(scene.id).heads['draft']==version.id
    assert repo.get_comment_set(scene.id) is None


@pytest.mark.parametrize('changes',[{'general':'x'*12001}, {'comments':[{'id':'a','instruction':' ','anchor':{'start':0,'end':1,'source_quote':'a','display_quote':'a'}}]}])
def test_comment_limits_are_explicit(changes):
    with pytest.raises(ValueError):CommentPayload.model_validate(changes)


def test_annotation_cannot_select_half_entity():
    text='А &amp; Б'
    notes=CommentPayload.model_validate({'comments':[{'id':'a','instruction':'Вказівка','anchor':{
        'start':3,'end':5,'source_quote':text[3:5],'display_quote':text[3:5]}}]})
    with pytest.raises(ValueError):validate_comment_set(text,'markdown',notes)


def test_concurrent_note_save_between_blob_and_publication_preserves_other_tab(tmp_path,monkeypatch):
    repo,_,scene,version=fixture(tmp_path)
    save(repo,scene,version,payload())
    original_write=repo.files.write
    changed=False
    def write_then_change_notes(relative,raw):
        nonlocal changed
        original_write(relative,raw)
        if not changed:
            changed=True
            save(repo,scene,version,payload(general='Інша вкладка.'),1)
    monkeypatch.setattr(repo.files,'write',write_then_change_notes)
    with pytest.raises(RevisionConflict):save(repo,scene,version,payload(),1,text=repo.read_text(version.id)+' Далі.')
    assert repo.get_scene(scene.id).heads['draft']==version.id
    assert repo.get_comment_set(scene.id).general=='Інша вкладка.'


def test_invalid_unpublished_origin_does_not_write_proof(tmp_path,monkeypatch):
    repo,_,scene,version=fixture(tmp_path)
    notes=payload();notes.comments[0].anchor.state='needs_review'
    notes.comments[0].anchor.origin_source=OriginSource(text='Інше джерело без цієї цитати.')
    writes=[]
    monkeypatch.setattr(repo.files,'write',lambda *args:writes.append(args))
    with pytest.raises(ValueError):save(repo,scene,version,notes)
    assert not writes
