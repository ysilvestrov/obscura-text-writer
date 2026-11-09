import json
from storygen.domain import SceneCreate,StoryCreate
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import build_dependency_snapshot,resolve_freshness

HERO='Роль: Головна героїня'


def setup(tmp_path,beats=('Початок: день 1, 20:00','Початок: день 1, 21:00')):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Час'))
    repo.publish_story_material(story.id,'characters_version_id',cards(repo,story.id,'A'),repo.get_story(story.id).revision)
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'С{i}',beats=b,character_ids=['A','B'])) for i,b in enumerate(beats)]
    return repo,story,scenes


def cards(repo,story_id,hero):
    data=[dict(schema_version=2,id=i,name=n,entries=[dict(id='e'+i,text=HERO if i==hero else 'Опис',availability='timeless',origin='author')]) for i,n in [('A','Анна'),('B','Богдан')]]
    return repo.save_version(story_id,None,'character_cards',json.dumps(data,ensure_ascii=False),[]).id


def memory_version(repo,story,scene):
    snap=build_dependency_snapshot(repo.context_view(story.id),scene.id,'memory',RoleSettings(provider=ProviderSettings(model='fake')),[])
    return repo.save_version(story.id,scene.id,'memory','{}',[],dependency_snapshot=snap),snap


def reasons(repo,story,ref):
    return [(r.reason,r.selector.field if r.selector else None) for r in resolve_freshness(repo.context_view(story.id),ref.id).reasons]


def test_snapshot_records_day_keys_and_tracked(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path)
    _,snap=memory_version(repo,story,s2)
    got={(s.kind,s.owner_id,s.field):s.expected for s in snap.selectors if s.field in {'memory_day_key','tracked_characters'}}
    assert got=={('story',story.id,'tracked_characters'):['A'],('scene',s2.id,'memory_day_key'):'day:1',('scene',s1.id,'memory_day_key'):'day:1'}


def test_beats_wording_change_keeps_memory_fresh(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path)
    ref,_=memory_version(repo,story,s2)
    repo.update_scene_plan(s2.id,'Початок: день 1, 21:00\nІнше формулювання подій',repo.get_scene(s2.id).revision)
    assert reasons(repo,story,ref)==[]


def test_day_key_change_makes_memory_stale(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path)
    ref,_=memory_version(repo,story,s2)
    repo.update_scene_plan(s2.id,'Початок: день 2, 08:00',repo.get_scene(s2.id).revision)
    assert ('selector_changed','memory_day_key') in reasons(repo,story,ref)


def test_tracked_change_makes_memory_stale(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path)
    ref,_=memory_version(repo,story,s2)
    repo.publish_story_material(story.id,'characters_version_id',cards(repo,story.id,'B'),repo.get_story(story.id).revision)
    assert ('selector_changed','tracked_characters') in reasons(repo,story,ref)


def test_comparison_scene_day_key_change_makes_memory_stale(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path)
    ref,_=memory_version(repo,story,s2)
    repo.update_scene_plan(s1.id,'Початок: день 0, 20:00',repo.get_scene(s1.id).revision)
    assert ('selector_changed','memory_day_key') in reasons(repo,story,ref)


def test_equivalent_date_spelling_keeps_memory_fresh(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,('Початок: 1.3.2024, 20:00','Початок: 01.03.2024, 21:00'))
    ref,snap=memory_version(repo,story,s2)
    assert {s.expected for s in snap.selectors if s.field=='memory_day_key'}=={'date:1.3.2024'}
    repo.update_scene_plan(s1.id,'Початок: 01.03.24, 20:00',repo.get_scene(s1.id).revision)
    assert reasons(repo,story,ref)==[]
