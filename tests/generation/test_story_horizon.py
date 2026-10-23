import json

import pytest
from pydantic import ValidationError

from storygen.domain import StoryCreate,SceneCreate,Scene
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.generation.context import build_context
from storygen.generation.models import StyleProfile
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot
from storygen.story_horizon import selected_plan_scenes


def role(mode='all',count=2,**kwargs):
    return RoleSettings(provider=ProviderSettings(model='fake'),context_tokens=262144,max_output_tokens=2048,
                        future_plan_mode=mode,future_plan_count=count,**kwargs)


@pytest.mark.parametrize('size',[7,15])
@pytest.mark.parametrize('mode,count,want',[('all',2,[2,3,4,5,6]),('next_n',2,[2,3,4]),('next_n',0,[2]),('current',99,[2])])
def test_projection_includes_current_and_exact_future_count(size,mode,count,want):
    scenes=[Scene(id=str(i),story_id='s',position=i,title=str(i)) for i in range(size)]
    expected=list(range(2,size)) if mode=='all' else want
    assert [x.position for x in selected_plan_scenes(scenes,scenes[2],role(mode,count))]==expected
    assert [x.position for x in selected_plan_scenes(scenes,scenes[-1],role(mode,count))]==[size-1]


def seeded(tmp_path,size=7):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Горизонт'))
    scenes=[]
    for index in range(size):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {index+1}',beats=f'УНІКАЛЬНИЙ_ПЛАН_{index+1}'))
        repo.update_scene_plan(scene.id,scene.beats,scene.revision)
        scenes.append(repo.get_scene(scene.id))
    return repo,repo.get_story(story.id),scenes


def test_excluded_plan_is_absent_from_text_refs_and_snapshot(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    ctx=build_context(repo,scenes[0].id,'brief',role('next_n',2))
    assert 'УНІКАЛЬНИЙ_ПЛАН_3' in ctx.user_text and 'УНІКАЛЬНИЙ_ПЛАН_4' not in ctx.user_text
    assert {s.heads['plan'] for s in scenes[:3]}<=set(ctx.input_refs)
    assert not {s.heads['plan'] for s in scenes[3:]} & set(ctx.input_refs)
    repo.update_scene_plan(scenes[6].id,'ДАЛЕКА_ЗМІНА',scenes[6].revision)
    assert not compare_snapshot(repo.context_view(story.id),ctx.dependency_snapshot)
    same=build_context(repo,scenes[0].id,'brief',role('next_n',2))
    assert same.fingerprint==ctx.fingerprint
    repo.update_scene_plan(scenes[2].id,'ВКЛЮЧЕНА_ЗМІНА',scenes[2].revision)
    assert compare_snapshot(repo.context_view(story.id),ctx.dependency_snapshot)


def test_order_window_ignores_hidden_swap_but_tracks_visible_swap_and_total(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    ctx=build_context(repo,scenes[0].id,'brief',role('next_n',2))
    ids=[s.id for s in scenes];ids[5],ids[6]=ids[6],ids[5]
    repo.reorder_scenes(story.id,ids,repo.get_story(story.id).revision)
    assert not compare_snapshot(repo.context_view(story.id),ctx.dependency_snapshot)
    ids[1],ids[2]=ids[2],ids[1]
    repo.reorder_scenes(story.id,ids,repo.get_story(story.id).revision)
    assert compare_snapshot(repo.context_view(story.id),ctx.dependency_snapshot)
    latest=build_context(repo,scenes[0].id,'brief',role('current'))
    repo.create_scene(story.id,SceneCreate(title='Нова'))
    changes=compare_snapshot(repo.context_view(story.id),latest.dependency_snapshot)
    assert any(c.selector and c.selector.field=='scene_count' for c in changes)


def test_current_warns_without_goal_and_goal_is_rendered_once_as_intention(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    ctx=build_context(repo,scenes[0].id,'brief',role('current'))
    assert any('орієнтир' in w.lower() and 'не задано' in w for w in ctx.context_warnings)
    from storygen.authoring.blueprints import update_story_profile
    update_story_profile(repo,story.id,StyleProfile(ending_goal='ФІНАЛ: двері залишаються відчиненими.'),repo.get_story(story.id).revision)
    actual=build_context(repo,scenes[0].id,'brief',role('current'))
    assert actual.user_text.count('ФІНАЛ: двері залишаються відчиненими.')==1
    assert 'АВТОРСЬКИЙ ОРІЄНТИР ФІНАЛУ' in actual.user_text
    assert 'не завершуйте весь твір' in actual.user_text
    assert not any('не задано' in w for w in actual.context_warnings)


def test_memory_and_diff_do_not_receive_goal_or_future_plans(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    from storygen.authoring.blueprints import update_story_profile
    update_story_profile(repo,story.id,StyleProfile(ending_goal='ТАЄМНИЙ_ФІНАЛ'),repo.get_story(story.id).revision)
    draft=repo.save_version(story.id,scenes[0].id,'draft','Поточна чернетка.',[])
    repo.set_head(scenes[0].id,'draft',draft.id,scenes[0].revision)
    prose=repo.save_version(story.id,scenes[0].id,'manual','Поточна проза.',[])
    repo.set_head(scenes[0].id,'prose',prose.id,repo.get_scene(scenes[0].id).revision)
    for stage,settings in [('memory',role('all')),('edit',role('all',edit_mode='diff')),('edit',role('all',edit_mode='patches'))]:
        ctx=build_context(repo,scenes[0].id,stage,settings)
        assert 'ТАЄМНИЙ_ФІНАЛ' not in ctx.user_text and 'УНІКАЛЬНИЙ_ПЛАН' not in ctx.user_text


def test_transitive_wide_brief_dependency_is_not_hidden_by_writer_horizon(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    wide=build_context(repo,scenes[0].id,'brief',role())
    brief=repo.save_version(story.id,scenes[0].id,'brief',json.dumps({'objective':'Лише початок','beats':['Початок']}),wide.input_refs,dependency_snapshot=wide.dependency_snapshot)
    repo.set_head(scenes[0].id,'brief',brief.id,scenes[0].revision)
    ctx=build_context(repo,scenes[0].id,'draft',role('current'))
    assert any('бриф' in w.lower() for w in ctx.context_warnings)
    repo.update_scene_plan(scenes[6].id,'Інший фінал',scenes[6].revision)
    assert compare_snapshot(repo.context_view(story.id),ctx.dependency_snapshot)


def test_old_settings_stay_all_and_invalid_horizons_are_rejected():
    old=RoleSettings(provider=ProviderSettings(model='old'))
    assert old.future_plan_mode=='all'
    for change in [{'future_plan_mode':'unknown'},{'future_plan_count':-1},{'future_plan_count':True},{'future_plan_count':1001}]:
        with pytest.raises(ValidationError):RoleSettings(provider=old.provider,**change)


def test_third_scene_window_uses_only_prefix_memory_and_three_plans(tmp_path):
    from storygen.memory.models import MemorySnapshot
    repo,story,scenes=seeded(tmp_path)
    sources=[]
    for scene in scenes[:2]:
        prose=repo.save_version(story.id,scene.id,'manual',f'Підтверджена подія {scene.position+1}.',[])
        repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
        sources.append(prose.id)
        memory=MemorySnapshot(source_prose_ids=list(sources))
        ref=repo.save_version(story.id,scene.id,'memory',memory.model_dump_json(),list(sources))
        repo.set_head(scene.id,'memory',ref.id,repo.get_scene(scene.id).revision)
    ctx=build_context(repo,scenes[2].id,'brief',role('next_n',2))
    assert set(sources)<=set(ctx.input_refs)
    for number in [3,4,5]:assert f'УНІКАЛЬНИЙ_ПЛАН_{number}' in ctx.user_text
    for number in [1,2,6,7]:assert f'УНІКАЛЬНИЙ_ПЛАН_{number}' not in ctx.user_text
    assert ctx.dependency_snapshot.scene_order==[s.id for s in scenes[:5]]


def test_trash_is_not_counted_as_a_future_scene(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    repo.set_scene_trashed(story.id,scenes[1].id,scenes[1].revision,False)
    ctx=build_context(repo,scenes[0].id,'brief',role('next_n',2))
    assert 'УНІКАЛЬНИЙ_ПЛАН_2' not in ctx.user_text
    assert 'УНІКАЛЬНИЙ_ПЛАН_4' in ctx.user_text and 'УНІКАЛЬНИЙ_ПЛАН_5' not in ctx.user_text
    assert scenes[1].heads['plan'] not in ctx.input_refs


def test_config_change_does_not_rewrite_frozen_context_or_legacy_snapshot(tmp_path):
    from storygen.generation.context import ContextBundle
    from storygen.dependency_models import DependencySnapshot
    repo,story,scenes=seeded(tmp_path)
    limited=build_context(repo,scenes[0].id,'brief',role('current'))
    frozen=limited.model_dump_json()
    repo.write_role_settings(story.id,{'planner':role().model_dump()},repo.get_story(story.id).revision)
    loaded=ContextBundle.model_validate_json(frozen)
    assert loaded.settings.future_plan_mode=='current' and loaded.user_text==limited.user_text
    assert not compare_snapshot(repo.context_view(story.id),loaded.dependency_snapshot)
    wide=build_context(repo,scenes[0].id,'brief',role())
    assert wide.fingerprint!=loaded.fingerprint and 'УНІКАЛЬНИЙ_ПЛАН_7' in wide.user_text
    raw=wide.dependency_snapshot.model_dump()
    for selector in raw['selectors']:selector.pop('future_count')
    legacy=DependencySnapshot.model_validate(raw)
    assert not compare_snapshot(repo.context_view(story.id),legacy)


def test_integrity_accepts_persisted_window_and_rejects_foreign_owner(tmp_path):
    from storygen.storage.integrity import check_integrity
    repo,story,scenes=seeded(tmp_path)
    ctx=build_context(repo,scenes[0].id,'brief',role('current'))
    ref=repo.save_version(story.id,scenes[0].id,'brief','{}',ctx.input_refs,dependency_snapshot=ctx.dependency_snapshot)
    assert check_integrity(tmp_path).ok
    other=repo.create_story(StoryCreate(title='Інший'))
    foreign=repo.create_scene(other.id,SceneCreate(title='Чужа'))
    payload=ref.model_dump()
    for selector in payload['dependency_snapshot']['selectors']:
        if selector['field']=='narrative_window':selector['owner_id']=foreign.id
    with repo.db.connection() as db:db.execute('UPDATE versions SET payload=? WHERE id=?',(json.dumps(payload),ref.id))
    assert 'invalid_snapshot' in {item.code for item in check_integrity(tmp_path).issues}


@pytest.mark.parametrize('mode',['patches','diff'])
def test_legacy_pending_editor_proposal_can_be_accepted_without_new_selector_field(tmp_path,mode):
    from tests.generation.test_sentence_groups import generated,CANDIDATE
    from storygen.generation.copyedit_review import copyedit_preview,select_copyedits
    repo,scene,attempt=generated(tmp_path,mode)
    for selector in attempt.context['dependency_snapshot']['selectors']:selector.pop('future_count')
    repo.save_attempt(attempt)
    preview=copyedit_preview(repo,scene.id,attempt.id)
    assert preview['can_apply']
    result=select_copyedits(repo,scene.id,attempt.id,preview['groups'][0]['indices'],preview['expected_revision'],preview['proposal_fingerprint'])
    assert repo.read_text(result['version'].id)==CANDIDATE
