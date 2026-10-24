from importlib.resources import files

from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.authoring.imports import SourceFile,import_sources
from storygen.characters.models import load_characters
from storygen.domain import StoryCreate
from storygen.web.app import create_app


def test_downloadable_templates_import_with_cast_and_overnight_timing(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    assets=files('storygen.web').joinpath('static','templates')
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        inputs=[]
        for name,kind in [('story-plan.md','source_plan'),('characters.md','source_characters')]:
            response=client.get('/static/templates/'+name)
            assert response.status_code==200
            assert response.content==assets.joinpath(name).read_bytes()
            response.content.decode('utf8')
            inputs.append(SourceFile(name=name,kind=kind,raw=response.content))
        repo=app.state.repo
        story=repo.create_story(StoryCreate(title='Перевірка шаблонів'))
        import_sources(repo,story.id,inputs)
        scenes=repo.list_scenes(story.id)
        assert len(scenes)==2
        assert scenes[0].title=='Зустріч' and scenes[1].title=='Нічна розмова'
        cards=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))
        assert [c.name for c in cards]==['Олена','Марко']
        assert all(s.character_ids==[c.id for c in cards] for s in scenes)
        assert 'Початок: день 1, 23:40' in scenes[1].beats
        assert 'Кінець: день 2, 00:20' in scenes[1].beats
        assert all(c.entries[0].availability=='unclassified' for c in cards)
        page=client.get('/stories/'+story.id).text
        assert 'href="/static/templates/story-plan.md" download="obscura-plan.md"' in page
        assert 'href="/static/templates/characters.md" download="obscura-characters.md"' in page
