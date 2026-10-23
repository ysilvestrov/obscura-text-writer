import json
import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.generation.context import build_context


def prepared(tmp_path,cast):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Склад'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',character_ids=cast))
    cards=[dict(schema_version=2,id=id,name=name,entries=[dict(id='e'+id,text=text,availability='timeless',origin='author')]) for id,name,text in [('A','Анна','ОПИС УЧАСНИЦІ'),('B','Богдан','СТОРОННІЙ ОПИС')]]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    return repo,story,scene


def test_only_participant_description_and_empty_never_means_all(tmp_path):
    from storygen.characters.context import character_material
    repo,story,scene=prepared(tmp_path,['A'])
    view=repo.context_view(story.id)
    text,_,_=character_material(view,view.get_story(story.id),view.get_scene(scene.id))
    assert 'ОПИС УЧАСНИЦІ' in text and 'СТОРОННІЙ ОПИС' not in text
    repo.update_scene_metadata(scene.id,{'character_ids':[]},repo.get_scene(scene.id).revision)
    view=repo.context_view(story.id)
    text,warnings,_=character_material(view,view.get_story(story.id),view.get_scene(scene.id))
    assert 'ОПИС' not in text and warnings


def test_raw_character_file_never_falls_back_to_full_scene_context(tmp_path):
    from storygen.authoring.imports import import_sources,SourceFile
    from storygen.characters.context import character_material
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Без карток'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',character_ids=['A']))
    import_sources(repo,story.id,[SourceFile(name='chars.md',kind='source_characters',raw='ПРИВАТНИЙ ПОВНИЙ ОПИС УСІХ'.encode())])
    view=repo.context_view(story.id)
    text,warnings,_=character_material(view,view.get_story(story.id),view.get_scene(scene.id))
    assert not text and warnings


@pytest.mark.parametrize('stage',['brief','memory','edit'])
def test_unknown_participant_blocks_generation_but_plan_saved(tmp_path,stage):
    import pytest
    repo,story,scene=prepared(tmp_path,['A'])
    text='Сцена 1: Нова назва\nПерсонажі: Анна, Невідомий.'
    saved=repo.update_scene_plan(scene.id,text,repo.get_scene(scene.id).revision)
    assert saved.beats==text and saved.title=='Нова назва'
    with pytest.raises(ValueError,match='Невідомий персонаж'):
        build_context(repo,scene.id,stage,RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches' if stage=='edit' else 'prose'))


@pytest.mark.parametrize('mode',['scene','story'])
def test_evaluator_descriptions_use_scope_cast(tmp_path,mode):
    from storygen.evaluation.story_adapter import build_evaluation_case
    repo,story,scene=prepared(tmp_path,['A'])
    prose=repo.save_version(story.id,scene.id,'manual','Анна діє.',[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    case=build_evaluation_case(repo,story.id,scene.id if mode=='scene' else None,mode)
    text='\n'.join(d.text for d in case.documents)
    assert 'ОПИС УЧАСНИЦІ' in text and 'СТОРОННІЙ ОПИС' not in text


@pytest.mark.parametrize('stage',['brief','draft','edit'])
def test_literary_requests_exclude_nonparticipants(tmp_path,stage):
    repo,story,scene=prepared(tmp_path,['A'])
    for head,kind,text in [('brief','brief','{"objective":"Подія","beats":["Подія"]}'),('draft','draft','Чернетка')]:
        ref=repo.save_version(story.id,scene.id,kind,text,[])
        repo.set_head(scene.id,head,ref.id,repo.get_scene(scene.id).revision)
    ctx=build_context(repo,scene.id,stage,RoleSettings(provider=ProviderSettings(model='fake'),context_tokens=32768))
    assert 'ОПИС УЧАСНИЦІ' in ctx.user_text and 'СТОРОННІЙ ОПИС' not in ctx.user_text


def test_evaluator_snapshot_tracks_participant_selection(tmp_path):
    from storygen.evaluation.story_adapter import build_evaluation_case
    from storygen.storage.snapshots import build_evaluation_snapshot,compare_snapshot
    repo,story,scene=prepared(tmp_path,['A'])
    prose=repo.save_version(story.id,scene.id,'manual','Анна діє.',[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    view=repo.context_view(story.id)
    case=build_evaluation_case(view,story.id,scene.id,'scene')
    snapshot=build_evaluation_snapshot(view,scene.id,case,'scene')
    repo.update_scene_metadata(scene.id,{'character_ids':['B']},repo.get_scene(scene.id).revision)
    assert any(c.selector and c.selector.field=='character_ids' for c in compare_snapshot(repo.context_view(story.id),snapshot))
