"""CHARACTER-EXTRACT (R-51): the `model` origin and quotes from scene prose as card sources."""
import json

import pytest

from storygen.characters.models import CharacterEntry, load_characters
from storygen.characters.service import read_character_material, save_character_material
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository

PROSE = 'Іва прийшла до воріт. Її також кликали Іва-Швидка.'
ERROR = 'Невірне джерело відомості персонажа'


def card(source_id=None, quote='Іва-Швидка', id=None):
    entry = {'text': 'Інше ім\'я: Іва-Швидка', 'origin': 'model', 'availability': 'timeless',
             'sources': [{'version_id': source_id, 'quote': quote}] if source_id else []}
    return {'schema_version': 2, **({'id': id} if id else {}), 'name': 'Іва', 'entries': [entry]}


def setup(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ферма'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ворота', beats='Іва приходить.'))
    prose = repo.save_version(story.id, scene.id, 'manual', PROSE, [])
    return repo, story, scene, prose


@pytest.mark.req('CHARACTER-EXTRACT')
def test_model_entry_needs_no_sources():
    entry = CharacterEntry(id='e', text='Інше ім\'я: Іва', origin='model')
    assert entry.origin == 'model' and entry.sources == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_prose_quote_source_saves(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    result = save_character_material(repo, story.id, [card(prose.id)], repo.get_story(story.id).revision)
    saved = repo.get_version(result['version_id'])
    assert saved.kind == 'character_cards' and prose.id not in saved.input_refs
    assert result['cards'][0]['entries'][0]['origin'] == 'model'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_prose_edit_does_not_stale_cards(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    result = save_character_material(repo, story.id, [card(prose.id)], repo.get_story(story.id).revision)
    new = repo.save_version(story.id, scene.id, 'manual', PROSE + ' Ще рядок.', [])
    repo.set_head(scene.id, 'prose', new.id, repo.get_scene(scene.id).revision)
    assert not repo.get_version(result['version_id']).stale


@pytest.mark.req('CHARACTER-EXTRACT')
def test_foreign_story_prose_rejected(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    other = repo.create_story(StoryCreate(title='Інший'))
    other_scene = repo.create_scene(other.id, SceneCreate(title='С', beats='Б'))
    foreign = repo.save_version(other.id, other_scene.id, 'manual', PROSE, [])
    # A version of another story is not even visible in this story's view: the existing, more specific message.
    with pytest.raises(ValueError, match='недоступне або належить іншому твору'):
        save_character_material(repo, story.id, [card(foreign.id)], repo.get_story(story.id).revision)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_incomplete_prose_rejected(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    with repo.db.connection() as db:
        row = db.execute('SELECT payload FROM versions WHERE id=?', (prose.id,)).fetchone()
        payload = json.loads(row[0])
        payload['complete'] = False
        db.execute('UPDATE versions SET payload=? WHERE id=?', (json.dumps(payload), prose.id))
    with pytest.raises(ValueError, match=ERROR):
        save_character_material(repo, story.id, [card(prose.id)], repo.get_story(story.id).revision)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_integrity_accepts_prose_sources(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    result = save_character_material(repo, story.id, [card(prose.id)], repo.get_story(story.id).revision)
    report = check_integrity(tmp_path)
    assert not [i for i in report.issues if i.code == 'invalid_characters']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_old_version_without_model_loads():
    raw = json.dumps([{'schema_version': 2, 'id': 'c', 'name': 'Іва', 'entries': [
        {'id': 'e', 'text': 'Вік: 30', 'origin': 'author'}]}])
    assert load_characters(raw)[0].entries[0].origin == 'author'
