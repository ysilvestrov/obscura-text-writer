import json
import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity
from storygen.storage.backup import create_backup,restore_backup
from storygen.characters.models import load_characters


@pytest.mark.parametrize('damage',['foreign_anchor','bad_quote','duplicate_id'])
def test_fsck_checks_character_semantics(tmp_path,damage):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Картки'))
    other=repo.create_story(StoryCreate(title='Інший'))
    scene=repo.create_scene(other.id,SceneCreate(title='Чужа'))
    source=repo.save_version(story.id,None,'source_characters','Анна носить ключ.',[])
    entry={'id':'e','text':'Ключ','origin':'imported','sources':[{'version_id':source.id,'quote':'носить ключ'}],
        'availability':'unclassified','available_from_scene_id':None}
    if damage=='foreign_anchor':entry.update(availability='from_scene',available_from_scene_id=scene.id)
    if damage=='bad_quote':entry['sources'][0]['quote']='Відсутня цитата'
    card={'schema_version':2,'id':'A','name':'Анна','entries':[entry]}
    if damage=='duplicate_id':card['entries'].append(entry.copy())
    repo.save_version(story.id,None,'character_cards',json.dumps([card]),[source.id])
    assert 'invalid_characters' in {i.code for i in check_integrity(tmp_path).issues}


def test_character_history_and_archived_anchor_survive_cold_restore(tmp_path):
    repo=Repository(tmp_path/'data');story=repo.create_story(StoryCreate(title='Історія'))
    scene=repo.create_scene(story.id,SceneCreate(title='Перша'))
    source=repo.save_version(story.id,None,'source_characters','Анна має ключ.',[])
    legacy=repo.save_version(story.id,None,'character_cards',json.dumps([{'id':'A','name':'Анна',
        'description':'Має ключ','sources':[{'version_id':source.id,'quote':'має ключ'}]}]),[source.id])
    cards=load_characters(repo.read_text(legacy.id));entry=cards[0].entries[0]
    entry.availability='from_scene';entry.available_from_scene_id=scene.id
    current=repo.save_version(story.id,None,'character_cards',json.dumps([c.model_dump() for c in cards]),[source.id])
    repo.publish_story_material(story.id,'characters_version_id',current.id,repo.get_story(story.id).revision)
    repo.set_scene_trashed(story.id,scene.id,repo.get_scene(scene.id).revision,False)
    report=check_integrity(repo.root)
    assert report.ok
    assert any('archived_character_anchor' in line for line in report.limitations)
    backup=create_backup(repo.root,tmp_path/'backup');restore_backup(backup,tmp_path/'restored')
    restored=Repository(tmp_path/'restored')
    assert load_characters(restored.read_text(legacy.id))[0].entries[0].availability=='unclassified'
    assert load_characters(restored.read_text(current.id))[0].entries[0].available_from_scene_id==scene.id
