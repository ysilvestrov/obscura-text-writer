import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.context import build_context
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.impact.planning import plan_impact,capture_target


def seeded(root):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Книга'))
    first=repo.create_scene(story.id,SceneCreate(title='Ранок',beats='Ранок'))
    second=repo.create_scene(story.id,SceneCreate(title='Вечір',beats='Вечір'))
    repo.create_scene(story.id,SceneCreate(title='Пізніше'))
    a=save_manual_prose(repo,first.id,'Марія знає про лист.',0)
    from storygen.storage.snapshots import build_author_baseline
    snapshot=build_author_baseline(repo.context_view(story.id),second.id)
    from storygen.dependency_models import DependencySelector
    snapshot.selectors.append(DependencySelector(kind="head",owner_id=first.id,field="prose",expected=a.id))
    snapshot.refs[a.id]=a.sha256
    text='Марія згадала лист.'
    ref=repo.save_version(story.id,second.id,'edited',text,list(snapshot.refs),dependency_snapshot=snapshot)
    repo.set_head(second.id,'prose',ref.id,repo.get_scene(second.id).revision)
    return repo,story,first,second,ref


def test_changed_predecessor_captures_old_and_new_without_future_prose(tmp_path):
    repo,story,first,second,ref=seeded(tmp_path)
    save_manual_prose(repo,first.id,'Марія не знає про лист.',repo.get_scene(first.id).revision)
    third=repo.list_scenes(story.id)[2]
    save_manual_prose(repo,third.id,'СЕКРЕТ МАЙБУТНЬОГО.',0)
    plan=plan_impact(repo.context_view(story.id))
    target=next(t for t in plan.targets if t.version_id==ref.id)
    assert any('не знає' in c.new_text and 'знає' in c.old_text for c in target.changes)
    assert 'СЕКРЕТ МАЙБУТНЬОГО' not in target.model_dump_json()
    assert target.blockers==[]


def test_distinct_historical_bases(tmp_path):
    repo,story,first,second,ref=seeded(tmp_path)
    before=capture_target(repo.context_view(story.id),ref.id)
    save_manual_prose(repo,first.id,'Марія не знає про лист.',repo.get_scene(first.id).revision)
    after=capture_target(repo.context_view(story.id),ref.id)
    assert before.fingerprint!=after.fingerprint
    assert after.changes


def test_noop_has_no_targets_and_missing_baseline_is_not_cleared(tmp_path):
    repo,story,first,second,ref=seeded(tmp_path)
    assert not plan_impact(repo.context_view(story.id)).targets
    with repo.db.connection() as db:
        old=repo._get(db,'versions',ref.id,type(ref));old.dependency_snapshot=None;old.stale=True
        db.execute('UPDATE versions SET payload=? WHERE id=?',(old.model_dump_json(),ref.id))
    target=capture_target(repo.context_view(story.id),ref.id)
    assert target.blockers

def test_manual_prose_records_prefix_for_later_revision_checks(tmp_path):
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Авторська редактура'))
    a=repo.create_scene(story.id,SceneCreate(title='Перша'));b=repo.create_scene(story.id,SceneCreate(title='Друга'))
    first=save_manual_prose(repo,a.id,'Марія знає.',0)
    later=save_manual_prose(repo,b.id,'Вона пригадала.',0)
    save_manual_prose(repo,a.id,'Марія забула.',repo.get_scene(a.id).revision)
    assert repo.get_version(later.id).stale
    target=capture_target(repo.context_view(story.id),later.id)
    assert not target.blockers and any('забула' in c.new_text for c in target.changes)

def test_temporal_character_projection_excludes_future_entries(tmp_path):
    import json
    from storygen.characters.models import CharacterRecord,CharacterEntry
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Часові відомості'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(3)]
    card=CharacterRecord(id='maria',name='Марія',entries=[CharacterEntry(id='now',text='Любить листи.',availability='timeless',origin='author'),CharacterEntry(id='later',text='МАЙБУТНЯ ТАЄМНИЦЯ',availability='from_scene',available_from_scene_id=scenes[2].id,origin='author')])
    old=repo.save_version(story.id,None,'character_cards',json.dumps([card.model_dump()],ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',old.id,repo.get_story(story.id).revision)
    repo.update_scene_metadata(scenes[1].id,{'character_ids':['maria']},repo.get_scene(scenes[1].id).revision)
    ref=save_manual_prose(repo,scenes[1].id,'Марія читає.',repo.get_scene(scenes[1].id).revision)
    card.entries[0].text='Уникає листів.'
    new=repo.save_version(story.id,None,'character_cards',json.dumps([card.model_dump()],ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',new.id,repo.get_story(story.id).revision)
    target=capture_target(repo.context_view(story.id),ref.id)
    assert not target.blockers
    assert 'МАЙБУТНЯ ТАЄМНИЦЯ' not in target.model_dump_json()
    assert any('Уникає' in c.new_text and 'Любить' in c.old_text for c in target.changes)

def test_explicit_author_acceptance_can_establish_legacy_prefix_basis(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Переглянута книга'))
    a=repo.create_scene(story.id,SceneCreate(title='Перша'));b=repo.create_scene(story.id,SceneCreate(title='Друга'))
    save_manual_prose(repo,a.id,'Лист прочитано.',0)
    legacy=repo.save_version(story.id,b.id,'manual','Марія згадала лист.',[])
    repo.set_head(b.id,'prose',legacy.id,0)
    preview=repo.preview_acceptance(b.id,legacy.id)
    repo.accept_version(b.id,legacy.id,preview.expected_revision,preview.preview_fingerprint)
    save_manual_prose(repo,a.id,'Лист не прочитано.',repo.get_scene(a.id).revision)
    assert repo.get_version(legacy.id).stale
    assert not capture_target(repo.context_view(story.id),legacy.id).blockers

def test_memory_review_input_preserves_historical_evidence_and_is_optional(tmp_path):
    from storygen.memory.journal import MemoryJournal
    from storygen.generation.impact_context import build_impact_context
    from tests.memory.test_forwarding import seeded as memory_seeded
    from storygen.authoring.blueprints import save_role_settings
    from storygen.providers.models import RoleSettings,ProviderSettings
    repo,story,scenes=memory_seeded(tmp_path)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic'),context_tokens=128000,max_input_chars=1000000),repo.get_story(story.id).revision)
    target=capture_target(repo.context_view(story.id),scenes[1].heads['prose'])
    assert target.memory_text and target.memory_evidence_status in {'current','historical'}
    context=build_impact_context(repo,target,'impact_check',dict(covered_change_ids=[],items=[],uncertainty=None))
    assert 'own_memory' in __import__('json').loads(context.user_text)
    assert context.fragments['impact_memory_included']=='true'


def test_oversized_optional_memory_does_not_block_prose_context(tmp_path):
    import json
    from storygen.generation.impact_context import build_impact_context
    from tests.memory.test_forwarding import seeded as memory_seeded
    from storygen.authoring.blueprints import save_role_settings
    from storygen.providers.models import RoleSettings,ProviderSettings
    repo,story,scenes=memory_seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='synthetic'),context_tokens=128000,max_input_chars=1000000)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    target=capture_target(repo.context_view(story.id),scenes[1].heads['prose'])
    assert target.memory_text
    base=build_impact_context(repo,target.model_copy(update={'memory_text':''}),'impact_check')
    size=len(json.dumps(base.api_request,ensure_ascii=False,separators=(',',':')))
    save_role_settings(repo,story.id,'planner',role.model_copy(update={'max_input_chars':size+1}),repo.get_story(story.id).revision)
    bounded=build_impact_context(repo,target,'impact_check')
    assert bounded.fragments['impact_memory_included']=='false'
    assert 'own_memory' not in json.loads(bounded.user_text)
    assert bounded.api_request==base.api_request
