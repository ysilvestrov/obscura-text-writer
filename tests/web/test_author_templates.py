from importlib.resources import files

from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.authoring.imports import SourceFile,import_sources
from storygen.characters.age import entry_age
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


def test_characters_template_marks_protagonist_and_explains_acquaintances(tmp_path):
    from storygen.characters.acquaintance import known_names_line, protagonist
    from storygen.storage.repository import Repository
    assets=files('storygen.web').joinpath('static','templates')
    text=assets.joinpath('characters.md').read_text(encoding='utf-8')
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Герой шаблону'))
    import_sources(repo,story.id,[SourceFile(name='characters.md',kind='source_characters',raw=text.encode())])
    cards=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))
    assert [c.name for c in cards]==['Олена','Марко']
    assert protagonist(cards,[])==(cards[0].id,[])
    hero_lines=[line for entry in cards[0].entries for line in entry.text.splitlines()]
    assert [known_names_line(line) for line in hero_lines if known_names_line(line) is not None]==[
        ['[Імена через кому','точно як у заголовках','видаліть рядок','якщо героїня знайомиться з усіма в історії.]']]
    assert not any(known_names_line(line) is not None for entry in cards[1].entries for line in entry.text.splitlines())
    assert '- Рядок «Знайомий з:» перелічує імена тих, кого персонаж знає ще до першої сцени; знайомство взаємне.' in text
    assert '- Головного героя позначте в його картці рядком «Роль у творі: Головна героїня»' in text


def test_character_template_age_line_matches_the_minors_guard(tmp_path):
    raw=files('storygen.web').joinpath('static','templates','characters.md').read_text('utf8')
    placeholder='Вік: [Число років на початку історії або «дорослий».]'
    assert raw.count(placeholder)==2
    app=create_app(AppSettings(data_dir=tmp_path))
    repo=app.state.repo
    verdicts=[]
    for value in (None,'34','дорослий','16'):
        text=raw if value is None else raw.replace(placeholder,'Вік: '+value)
        story=repo.create_story(StoryCreate(title='Вік '+str(value)))
        import_sources(repo,story.id,[SourceFile(name='characters.md',kind='source_characters',raw=text.encode('utf8'))])
        cards=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))
        verdicts.append([entry_age(c.entries[0].text) for c in cards])
    assert verdicts==[['unknown','unknown'],['adult','adult'],['adult','adult'],['minor','minor']]
    plan=files('storygen.web').joinpath('static','templates','story-plan.md').read_text('utf8')
    assert 'рейтинг' in plan and 'налаштуваннях твору' in plan
