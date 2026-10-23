import json
import pytest
from storygen.domain import StoryCreate,SceneCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.authoring.imports import suggest_scene_sections,SourceFile,import_sources


def cards(repo,story):
    payload=[dict(schema_version=2,id=id,name=name,entries=[dict(id='entry-'+id,text='опис-'+id,availability='timeless',origin='author')]) for id,name in [('lera','Олена'),('maria','Наталя'),('other','Остап')]]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(payload,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    return ref


@pytest.mark.parametrize('heading',['Сцена 3: Дзвінок колеги. Дзеркало','## Сцена 3. Дзвінок колеги. Дзеркало','**Сцена 3: Дзвінок колеги. Дзеркало**'])
def test_import_title_without_markup(heading):
    scene=suggest_scene_sections(heading+'\nПерсонажі: Олена, Наталя.')[0]
    assert scene.title=='Дзвінок колеги. Дзеркало'
    assert scene.beats.startswith(heading)


@pytest.mark.parametrize('label',['Персонажі','Хто бере участь'])
def test_plan_save_extracts_title_and_participants_atomically(tmp_path,label):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));cards(repo,story)
    scene=repo.create_scene(story.id,SceneCreate(title='Початкова'))
    text=f'Сцена 3: Дзвінок колеги. Дзеркало\n{label}: олена, Наталя.\nДії: дзвінок.'
    saved=repo.update_scene_plan(scene.id,text,scene.revision)
    assert saved.title=='Дзвінок колеги. Дзеркало' and saved.character_ids==['lera','maria']
    assert saved.beats==text and repo.read_text(saved.heads['plan'])==text
    with pytest.raises(RevisionConflict):repo.update_scene_plan(scene.id,'Сцена 3: Інша\nПерсонажі: Остап',scene.revision)
    assert repo.get_scene(scene.id).title==saved.title


def test_cast_resolved_when_cards_created_after_import(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    text='Сцена 3: Дзвінок\nХто бере участь: Олена, Наталя.'
    import_sources(repo,story.id,[SourceFile(name='plan.md',raw=text.encode())])
    scene=repo.list_scenes(story.id)[0]
    assert not scene.character_ids
    cards(repo,story)
    assert repo.get_scene(scene.id).character_ids==['lera','maria']


def test_no_metadata_preserves_manual_selection_and_explicit_empty_clears(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));cards(repo,story)
    scene=repo.create_scene(story.id,SceneCreate(title='Авторська назва',character_ids=['lera']))
    saved=repo.update_scene_plan(scene.id,'Дії: дзвінок.',scene.revision)
    assert saved.title==scene.title and saved.character_ids==['lera']
    empty=repo.update_scene_plan(scene.id,'Персонажі:\nДії: пейзаж.',saved.revision)
    assert empty.character_ids==[]


def test_exact_ids_dedup_and_ambiguous_names():
    from storygen.scene_description import resolve_participants
    from types import SimpleNamespace
    values=[SimpleNamespace(id='one',name='Наталя'),SimpleNamespace(id='two',name='Наталя')]
    ids,problems=resolve_participants(['one','one','Наталя','Невідомий'],values)
    assert ids==['one'] and len(problems)==2



def test_create_and_blueprint_use_same_description_parser(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));ref=cards(repo,story)
    scene=repo.create_scene(story.id,SceneCreate(title='Початкова',beats='Сцена 1: Назва\nПерсонажі: maria; Олена, maria.'))
    assert scene.title=='Назва' and scene.character_ids==['maria','lera']
    second=repo.create_story(StoryCreate(title='Новий'))
    canonical=repo.save_version(second.id,None,'canon','Канон',[])
    chars=repo.save_version(second.id,None,'character_cards',repo.read_text(ref.id),[])
    text='Сцена 3: Дзеркало\nПерсонажі: Наталя.'
    plan=repo.save_version(second.id,None,'scene_plan',text,[])
    repo.publish_blueprint(second.id,canonical.id,chars.id,[(SceneCreate(title='Стара',beats=text),plan)],second.revision)
    planned=repo.list_scenes(second.id)[0]
    assert planned.title=='Дзеркало' and planned.character_ids==['maria']



def test_card_resync_invalidates_legacy_derived_head(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));ref=cards(repo,story)
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Персонажі: Олена'))
    legacy=repo.save_version(story.id,scene.id,'brief','{"objective":"Стара версія","beats":["Подія"]}',[])
    repo.set_head(scene.id,'brief',legacy.id,scene.revision)
    payload=json.loads(repo.read_text(ref.id));payload[0]['id']='new-lera';payload[0]['entries'][0]['id']='new-entry'
    changed=repo.save_version(story.id,None,'character_cards',json.dumps(payload,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',changed.id,repo.get_story(story.id).revision)
    assert repo.get_scene(scene.id).character_ids==['new-lera']
    assert repo.get_version(legacy.id).stale
