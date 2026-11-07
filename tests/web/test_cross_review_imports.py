import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.authoring.imports import SourceFile,import_sources
from storygen.authoring.blueprints import apply_blueprint
from storygen.domain import StoryCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.generation.models import StoryBlueprint
from storygen.generation.prepare_sources import prepare_sources


def upload(repo,id,text,kind='source_plan'):
    return import_sources(repo,id,[SourceFile(name='file.md',raw=text.encode(),kind=kind)])


def test_failed_character_file_never_claims_published_cards(tmp_path,monkeypatch):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();id=story['id']
        upload(app.state.repo,id,'## Анна\nФакт','source_characters')
        original=app.state.repo.publish_import;count=0
        def publish(*args):
            nonlocal count
            count+=1
            if count==2:raise RevisionConflict('synthetic conflict')
            return original(*args)
        monkeypatch.setattr(app.state.repo,'publish_import',publish)
        response=client.post(f'/api/stories/{id}/sources',files=[('plan',('a.md','Сцена 1: Ранок\nПлан'.encode())),('characters',('b.md','## Марія\nНовий факт\n## Анна\nДубль'.encode()))])
        assert response.status_code==200
        data=response.json();failed=data['files'][1]
        assert data['partial'] is True
        assert failed['status']=='failed' and failed['created_character_cards']==0
        assert failed['warnings']==[] and failed['skipped_character_names']==[]
        assert not any('Створено нових карток' in w for w in data['warnings'])
        assert failed['source_id'] is None and failed['version_id'] is None


def test_appended_plan_preserves_current_canon_and_cards_citing_old_plan(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Канон'))
    first=upload(repo,story.id,'Сцена 1: Ранок\nПерший факт')
    current=repo.get_story(story.id)
    proposal=StoryBlueprint.model_validate(dict(canon='Канон',characters=[dict(id='anna',name='Анна',description='Перший факт',sources=[dict(version_id=first.version_ids[0],quote='Перший факт')])],scenes=[dict(title='Ранок')]))
    current=apply_blueprint(repo,story.id,proposal,current.revision)
    upload(repo,story.id,'Сцена 2: Вечір\nДругий факт')
    assert not repo.get_version(current.canon_version_id).stale
    assert not repo.get_version(current.characters_version_id).stale
    view=repo.context_view(story.id)
    assert all(not ref.stale for ref in prepare_sources(view,view.story))


def test_explicit_create_number_is_not_silently_dropped(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();id=story['id']
        response=client.post(f'/api/stories/{id}/scenes',json={'title':'X','author_scene_number':5})
        assert response.status_code==200
        scene=response.json()
        assert scene['author_scene_number']==5
        bad=client.post(f'/api/stories/{id}/scenes',json={'title':'X','author_scene_number':6,'beats':'Сцена 7: Інша'})
        assert bad.status_code==400


@pytest.mark.parametrize('extra',[1,1025])
def test_oversized_uploads_return_413_before_publication(tmp_path,extra):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();id=story['id']
        response=client.post(f'/api/stories/{id}/sources',files={'plan':('large.md',b'x'*(2*1024*1024+extra))})
        assert response.status_code==413
        assert app.state.repo.list_source_files(id)==[]


def test_first_runtime_conflict_returns_409_per_file_results(tmp_path,monkeypatch):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();id=story['id']
        def conflict(*args):raise RevisionConflict('synthetic conflict')
        monkeypatch.setattr(app.state.repo,'publish_import',conflict)
        response=client.post(f'/api/stories/{id}/sources',files=[('plan',(name,b'Plan')) for name in ['a.md','b.md']])
        assert response.status_code==409
        data=response.json()
        assert data['partial'] is False
        assert [f['status'] for f in data['files']]==['failed','not_processed']
        assert data['files'][0]['error']
        assert [f['source_id'] for f in data['files']]==[None,None]
        assert app.state.repo.list_source_files(id)==[]


def test_duplicate_numbered_file_does_not_stale_current_heads(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Дубль'))
    text='Сцена 1: Ранок\nПерший план'
    upload(repo,story.id,text);scene=repo.list_scenes(story.id)[0]
    prose=save_manual_prose(repo,scene.id,'Ручна проза.',scene.revision)
    before=repo.get_scene(scene.id)
    assert not repo.get_version(prose.id).stale
    upload(repo,story.id,text)
    after=repo.get_scene(scene.id)
    assert after.heads==before.heads
    assert not repo.get_version(after.heads['plan']).stale
    assert not repo.get_version(after.heads['prose']).stale


@pytest.mark.parametrize('heading',['## **','Сцена 3: **'])
def test_empty_cleaned_heading_uses_default_title(tmp_path,heading):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Розмітка'))
    result=upload(repo,story.id,heading+'\nОпис')
    assert len(result.created_scene_ids)==1
    assert repo.list_scenes(story.id)[0].title=='Сцена 1'
