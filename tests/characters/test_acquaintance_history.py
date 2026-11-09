import json
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.models import WritersBrief
from storygen.characters.acquaintance import acquaintances,lineage_brief


def setup(tmp_path,cards_text=None,count=3,casts=None):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Знайомства'))
    names=[('A','Анна'),('B','Богдан'),('C','Віра'),('Z','Галина')]
    cards=[dict(schema_version=2,id=i,name=n,entries=[dict(id='e'+i,text=(cards_text or {}).get(i,'Опис'),availability='timeless',origin='author')]) for i,n in names]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    casts=casts or [['A','B']]*count
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'С{i}',character_ids=cast)) for i,cast in enumerate(casts)]
    return repo,story,scenes


def brief(repo,story,scene,introduced=None,**kw):
    data=dict(objective='o',beats=['b'])
    if introduced is not None:data['introduced']=introduced
    return repo.save_version(story.id,scene.id,'brief',WritersBrief(**data).model_dump_json(),[])


def prose(repo,story,scene,chain=None,kind='manual'):
    ref=repo.save_version(story.id,scene.id,kind,'Текст.',[chain] if chain else [])
    repo.set_head(scene.id,'prose',ref.id,repo.get_scene(scene.id).revision)
    return ref


def with_brief_prose(repo,story,scene,introduced=None):
    b=brief(repo,story,scene,introduced)
    d=repo.save_version(story.id,scene.id,'draft','Чернетка.',[b.id])
    e=prose(repo,story,scene,d.id,'edited')
    return b,e


def run(repo,story,index):
    view=repo.context_view(story.id)
    return acquaintances(view,view.get_story(story.id),view.list_scenes(story.id)[index])


def test_lineage_brief_wins_over_newer_head(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B','C'],['A','B','C']])
    b1,_=with_brief_prose(repo,story,s1,['B'])
    b2=brief(repo,story,s1,[])
    repo.set_head(s1.id,'brief',b2.id,repo.get_scene(s1.id).revision)
    view=repo.context_view(story.id)
    assert lineage_brief(view,view.get_scene(s1.id)).id==b1.id
    assert run(repo,story,1).known=={'B':1}


def test_fallback_for_prose_without_brief_and_legacy_brief(tmp_path):
    repo,story,(s1,s2,s3)=setup(tmp_path,casts=[['A','B'],['A','C'],['A']])
    prose(repo,story,s1)
    with_brief_prose(repo,story,s2)
    assert run(repo,story,2).known=={'B':1,'C':2}


def test_explicit_empty_introduced_keeps_unknown(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B'],['A']])
    with_brief_prose(repo,story,s1,[])
    assert 'B' not in run(repo,story,1).known


def test_ids_outside_cast_and_hero_ignored(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B'],['A']])
    with_brief_prose(repo,story,s1,['A','Z','C'])
    assert run(repo,story,1).known=={}


def test_scene_without_accepted_prose_adds_nothing(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,casts=[['A','B'],['A']])
    b=brief(repo,story,s1,['B'])
    d=repo.save_version(story.id,s1.id,'draft','Ч.',[b.id])
    repo.set_head(s1.id,'draft',d.id,repo.get_scene(s1.id).revision)
    assert run(repo,story,1).known=={}


def test_hero_absent_from_past_scene_adds_nothing(tmp_path):
    repo,story,(s1,s2,s3)=setup(tmp_path,casts=[['A'],['B','C'],['A']])
    prose(repo,story,s2)
    assert run(repo,story,2).known=={}


def test_reorder_changes_scene_numbers(tmp_path):
    repo,story,(s1,s2,s3)=setup(tmp_path,casts=[['A'],['A','B'],['A']])
    prose(repo,story,s2)
    assert run(repo,story,2).known=={'B':2}
    repo.reorder_scenes(story.id,[s2.id,s1.id,s3.id],repo.get_story(story.id).revision)
    assert run(repo,story,2).known=={'B':1}
    repo.reorder_scenes(story.id,[s1.id,s2.id,s3.id],repo.get_story(story.id).revision)
    assert run(repo,story,2).known=={'B':2}


def test_pre_story_tag_wins_with_none(tmp_path):
    repo,story,(s1,s2)=setup(tmp_path,cards_text={'B':'Знайомий з: Анна'},casts=[['A','B'],['A']])
    prose(repo,story,s1)
    result=run(repo,story,1)
    assert result.hero_id=='A' and result.known=={'B':None}


def test_no_cards_returns_empty(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Т'))
    scene=repo.create_scene(story.id,SceneCreate(title='С',character_ids=['A']))
    view=repo.context_view(story.id)
    r=acquaintances(view,view.get_story(story.id),view.list_scenes(story.id)[0])
    assert (r.hero_id,r.known,r.warnings)==(None,{},[])
