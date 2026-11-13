"""EXPORT-001-S06: a readable Markdown file with the current plan and characters."""
import pytest
from storygen.application.plan_export import plan_markdown
from storygen.authoring.imports import SourceFile, import_sources
from storygen.authoring.trash import trash_scene
from storygen.characters.models import load_characters
from storygen.characters.service import save_character_material
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository


def upload(repo, story_id, text, kind):
    import_sources(repo, story_id, [SourceFile(name='file.md', raw=text.encode(), kind=kind)])


def story_with_plan(tmp_path, language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Маяк *на* пристані', language=language))
    upload(repo, story.id, 'Задум: світло в тумані.\n## Сцена 1: Ранок\nПерсонажі: Анна\nЩо відбувається: лист.\n## Сцена 2: Шторм\nПерсонажі: Анна\nЩо відбувається: хвилі.\n## Сцена 3: Кінець\nЩо відбувається: тиша.', 'source_plan')
    upload(repo, story.id, '## Анна\nДоглядачка маяка.', 'source_characters')
    return repo, repo.get_story(story.id)


@pytest.mark.req('EXPORT-001')
def test_plan_and_characters_in_reading_order(tmp_path):
    repo, story = story_with_plan(tmp_path)
    first, second, third = repo.list_scenes(story.id)
    # A saved plan version wins over the imported beats.
    plan = repo.save_version(story.id, second.id, 'scene_plan', 'Шторм переписано автором.', [])
    repo.set_head(second.id, 'plan', plan.id, repo.get_scene(second.id).revision)
    cards = [c.model_dump() for c in load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))]
    cards[0]['entries'].append(dict(id=None, text='Знає про лист.', origin='author', sources=[], availability='from_scene', available_from_scene_id=second.id))
    cards[0]['entries'].append(dict(id=None, text='Бачила корабель.', origin='author', sources=[], availability='from_scene', available_from_scene_id=third.id))
    save_character_material(repo, story.id, cards, repo.get_story(story.id).revision)
    trash_scene(repo, story.id, third.id, repo.get_scene(third.id).revision)
    name, content = plan_markdown(repo, story.id)
    text = content.decode('utf-8')
    assert name.endswith('.md')
    assert text.startswith(r'# Маяк \*на\* пристані' + '\n')
    assert text.index('## План') < text.index('Задум: світло в тумані.') < text.index('### Сцена 1: Ранок') < text.index('### Сцена 2: Шторм') < text.index('## Персонажі')
    assert 'Що відбувається: лист.' in text  # imported beats, no plan version yet
    assert 'Шторм переписано автором.' in text and 'Що відбувається: хвилі.' not in text
    assert 'Кінець' not in text and 'тиша' not in text  # trashed scene
    assert '### Анна' in text and 'Доглядачка маяка.' in text
    assert '- Знає про лист. (від сцени 2: Шторм)' in text
    assert '- Бачила корабель. (від сцени в кошику)' in text
    assert 'version_id' not in text


@pytest.mark.req('EXPORT-001')
def test_empty_plan_and_no_characters_are_marked(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Порожньо'))
    repo.create_scene(story.id, SceneCreate(title='Перша'))
    text = plan_markdown(repo, story.id)[1].decode('utf-8')
    assert '### Сцена 1: Перша\n\n_План не створено._' in text
    assert '## Персонажі\n\n_Персонажів не додано._' in text


@pytest.mark.req('EXPORT-001')
def test_english_story_uses_english_labels(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Pier', language='en'))
    repo.create_scene(story.id, SceneCreate(title='First'))
    text = plan_markdown(repo, story.id)[1].decode('utf-8')
    for label in ['## Plan', '### Scene 1: First', '_No plan yet._', '## Characters', '_No characters yet._']:
        assert label in text, label


@pytest.mark.req('EXPORT-001')
def test_route_serves_markdown_attachment(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Маяк'}).json()
        response = client.get(f"/api/stories/{story['id']}/plan.md")
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/markdown')
        assert 'attachment' in response.headers['content-disposition'] and ".md" in response.headers['content-disposition']
        assert response.text.startswith('# Маяк\n')
        assert client.get('/api/stories/missing/plan.md').status_code == 404
        assert not list((tmp_path).rglob('*.manifest.json'))  # nothing stored
