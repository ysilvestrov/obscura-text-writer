import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.authoring.imports import SourceFile,import_sources
from storygen.domain import StoryCreate, RevisionConflict
from storygen.storage.repository import Repository
from storygen.characters.models import load_characters


def upload(repo,id,text,kind='source_plan'):
    return import_sources(repo,id,[SourceFile(name='file.md',raw=text.encode(),kind=kind)])


def test_mixed_numbered_and_unnumbered_import_preserves_active_plan(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    upload(repo,story.id,'Вступ\n## Сцена 2. Зустріч\nСтарий опис')
    first=repo.list_scenes(story.id)[0]
    result=upload(repo,story.id,'Новий вступ\n## Сцена 02: Друзі\nНе замінювати\n## Сцена 3: Зустріч\nНовий опис\n## Інтерлюдія\nТиша')
    assert result.skipped_scene_numbers==[2]
    assert len(result.created_scene_ids)==2
    scenes=repo.list_scenes(story.id)
    assert scenes[0].heads==first.heads and scenes[0].beats==first.beats
    assert [s.author_scene_number for s in scenes]==[2,3,None]
    assert [s.target_words for s in scenes][1:]==[1000,1000]
    text=repo.read_text(repo.active_source(story.id,'source_plan').id)
    assert text=='Вступ\n## Сцена 2. Зустріч\nСтарий опис\n\n## Сцена 3: Зустріч\nНовий опис\n## Інтерлюдія\nТиша'
    active=repo.active_source(story.id,'source_plan').id
    upload(repo,story.id,'Сцена 2: Інакша\nІнший текст')
    assert repo.active_source(story.id,'source_plan').id==active
    upload(repo,story.id,'## Інтерлюдія\nТиша')
    assert len(repo.list_scenes(story.id))==4


def test_characters_add_only_new_names_and_keep_exact_existing_payload(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    upload(repo,story.id,'## Анна\nСтарий опис','source_characters')
    before=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))[0]
    result=upload(repo,story.id,'## АННА\nНовий опис\n## Марія\nДругий опис\n## марія\nДубль','source_characters')
    cards=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))
    assert cards[0]==before
    assert [c.name for c in cards]==['Анна','Марія']
    assert result.created_character_cards==1
    assert result.skipped_character_names==['АННА','марія']
    head=repo.get_story(story.id).characters_version_id
    upload(repo,story.id,'## Анна\nНе замінювати','source_characters')
    assert repo.get_story(story.id).characters_version_id==head


def test_multipart_reports_partial_without_retry_and_prevalidates_all(tmp_path,monkeypatch):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();url=f"/api/stories/{story['id']}/sources"
        bad=client.post(url,files=[('plan',('a.md',b'Plan')),('plan',('bad.exe',b'bad'))])
        assert bad.status_code==400
        assert app.state.repo.list_source_files(story['id'])==[]
        original=app.state.repo.publish_import;count=0
        def publish(*args):
            nonlocal count
            count+=1
            if count==2:raise ValueError('synthetic fault')
            return original(*args)
        monkeypatch.setattr(app.state.repo,'publish_import',publish)
        response=client.post(url,files=[('plan',(name,b'Plan')) for name in ['a.md','b.md','c.md']])
        assert response.status_code==200,response.text
        data=response.json()
        assert data['partial'] and [f['status'] for f in data['files']]==['imported','failed','not_processed']
        scenes=app.state.repo.list_scenes(story['id'])
        assert len(scenes)==1
        assert data['created_scene_ids']==[scenes[0].id]
        assert data['files'][0]['created_scene_ids']==[scenes[0].id]
        assert data['files'][0]['source_id']==app.state.repo.list_source_files(story['id'])[0]['id']
        assert data['files'][0]['version_id']==app.state.repo.list_source_files(story['id'])[0]['version_id']
        assert data['files'][1]['error']
        assert [f['source_id'] for f in data['files'][1:]]==[None,None]
        assert [f['version_id'] for f in data['files'][1:]]==[None,None]
        assert data['files'][2]['error'] is None


def test_card_version_citations_remain_editable_and_extendable(tmp_path):
    from storygen.characters.service import save_character_material,preview_character_material
    from storygen.domain import SceneCreate
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Цитати'))
    upload(repo,story.id,'## Анна\nПерший факт','source_characters')
    old=repo.get_story(story.id).characters_version_id
    current=repo.get_story(story.id)
    cards=[c.model_dump() for c in load_characters(repo.read_text(old))]
    entry=cards[0]['entries'][0]
    entry['sources']=[{'version_id':old,'quote':'Перший факт'}]
    saved=save_character_material(repo,story.id,cards,current.revision)
    assert not repo.get_version(saved['version_id']).stale
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',character_ids=[saved['cards'][0]['id']]))
    assert 'Перший факт' in preview_character_material(repo,story.id,saved['cards'],scene.id)['text']
    added=upload(repo,story.id,'## Марія\nДругий факт','source_characters')
    assert added.created_character_cards==1


def test_blueprint_citing_current_cards_publishes_fresh_material(tmp_path):
    from storygen.authoring.blueprints import apply_blueprint
    from storygen.generation.models import StoryBlueprint
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Пропозиція'))
    upload(repo,story.id,'## Анна\nПочатковий факт','source_characters')
    story=repo.get_story(story.id)
    proposal=StoryBlueprint.model_validate(dict(canon='Канон',characters=[dict(id='anna',name='Анна',description='Початковий факт',sources=[dict(version_id=story.characters_version_id,quote='Початковий факт')])],scenes=[dict(title='Сцена',beats='План')]))
    saved=apply_blueprint(repo,story.id,proposal,story.revision)
    assert not repo.get_version(saved.canon_version_id).stale
    assert not repo.get_version(saved.characters_version_id).stale


def test_appending_plan_keeps_previous_authored_plan_usable(tmp_path):
    from storygen.generation.context import build_context
    from storygen.providers.models import RoleSettings,ProviderSettings
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Плани'))
    upload(repo,story.id,'Сцена 1: Ранок\nПерший план')
    first=repo.list_scenes(story.id)[0]
    upload(repo,story.id,'Сцена 2: Вечір\nДругий план')
    assert not repo.get_version(first.heads['plan']).stale
    build_context(repo,first.id,'brief',RoleSettings(provider=ProviderSettings(model='synthetic')))


def test_unnumbered_future_sections_are_not_global_instructions(tmp_path):
    from storygen.generation.context import build_context
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.storage.snapshots import source_preamble
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Горизонт'))
    upload(repo,story.id,'Вступ\n## Початок\nПоточна сцена\n## Інтерлюдія\nFUTURE_SECRET\n## Сцена 2: Друга\nТекст')
    first=repo.list_scenes(story.id)[0]
    context=build_context(repo,first.id,'brief',RoleSettings(provider=ProviderSettings(model='synthetic'),future_plan_mode='current'))
    assert 'FUTURE_SECRET' not in context.user_text
    view=repo.context_view(story.id)
    assert source_preamble(view,view.active_source(story.id,'source_plan'))==view.active_source(story.id,'source_plan').id

@pytest.mark.parametrize('fault', [KeyError, TypeError])
def test_unexpected_failure_after_first_file_reports_partial(tmp_path, monkeypatch, fault):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Synthetic'}).json()
        original=app.state.repo.publish_import
        count=0
        def publish(*args):
            nonlocal count
            count+=1
            if count==2: raise fault('private details')
            return original(*args)
        monkeypatch.setattr(app.state.repo,'publish_import',publish)
        response=client.post(f"/api/stories/{story['id']}/sources",files=[('plan',(name,b'Plan')) for name in ('a.md','b.md','c.md')])
        assert response.status_code==200
        data=response.json()
        assert data['partial'] and [f['status'] for f in data['files']]==['imported','failed','not_processed']
        assert data['active_sources']==dict(app.state.repo.context_view(story['id']).sources)
        assert 'private details' not in response.text

@pytest.mark.parametrize('fault,status', [(ValueError,400), (RevisionConflict,409)])
def test_first_import_failure_reports_current_active_sources(tmp_path,monkeypatch,fault,status):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Synthetic'}).json()
        url=f"/api/stories/{story['id']}/sources"
        assert client.post(url,files=[('plan',('a.md',b'Plan'))]).status_code==200
        active=dict(app.state.repo.context_view(story['id']).sources)
        def fail(*args): raise fault('private details')
        monkeypatch.setattr(app.state.repo,'publish_import',fail)
        response=client.post(url,files=[('plan',('b.md',b'Plan'))])
        assert response.status_code==status
        data=response.json()
        assert data['active_sources']==active
        assert data['warnings'] and data['files'][0]['status']=='failed'
        assert 'private details' not in response.text
