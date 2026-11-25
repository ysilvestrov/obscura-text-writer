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


def setup(tmp_path, kind='manual'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ферма'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ворота', beats='Іва приходить.'))
    prose = repo.save_version(story.id, scene.id, kind, PROSE, [])
    return repo, story, scene, prose


@pytest.mark.req('CHARACTER-EXTRACT')
def test_model_entry_needs_no_sources():
    entry = CharacterEntry(id='e', text='Інше ім\'я: Іва', origin='model')
    assert entry.origin == 'model' and entry.sources == []


@pytest.mark.req('CHARACTER-EXTRACT')
@pytest.mark.parametrize('kind', ['manual', 'edited'])
def test_prose_quote_source_saves(tmp_path, kind):
    repo, story, scene, prose = setup(tmp_path, kind)
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


@pytest.mark.req('CHARACTER-EXTRACT')
def test_plan_source_stays_a_ref_next_to_prose(tmp_path):
    repo, story, scene, prose = setup(tmp_path)
    plan = repo.save_version(story.id, None, 'source_plan', 'Іва — героїня.', [])
    payload = card(prose.id)
    payload['entries'].append({'text': 'Героїня', 'origin': 'imported', 'availability': 'timeless',
                               'sources': [{'version_id': plan.id, 'quote': 'героїня'}]})
    result = save_character_material(repo, story.id, [payload], repo.get_story(story.id).revision)
    assert repo.get_version(result['version_id']).input_refs == [plan.id]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_card_editor_shows_the_model_origin():
    # An accepted entry has origin `model`: the editor's origin list must name it (in both languages) instead of showing
    # a blank choice; the author cannot newly mark an entry as the model's.
    import json
    from pathlib import Path
    static = Path(__file__).resolve().parents[2] / 'src/storygen/web/static'
    source = (static / 'characters.js').read_text(encoding='utf-8')
    assert 'get model(){return t("characters.origin_model")}' in source
    assert "value==='model'&&entry.origin!=='model'" in source
    catalog = json.loads((static / 'i18n.json').read_text(encoding='utf-8'))
    assert (catalog['uk']['characters.origin_model'], catalog['en']['characters.origin_model']) == ('Від моделі', 'From model')
