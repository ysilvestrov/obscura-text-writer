import json
import pytest
from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.generation.context import build_context
from storygen.generation.models import WritersBrief
from storygen.memory.models import MemorySnapshot
from storygen.characters.acquaintance import acquaintance_material,unexpected_introduced

NAMES=[('A','Анна'),('B','Богдан'),('C','Віра')]


def settings(stage):
    return RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches' if stage=='edit' else 'prose',context_tokens=32768)


def prepared(tmp_path,casts,texts=None):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Знайомства'))
    cards=[dict(schema_version=2,id=i,name=n,entries=[dict(id='e'+i,text=(texts or {}).get(i,'Опис'),availability='timeless',origin='author')]) for i,n in NAMES]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'С{i}',character_ids=cast)) for i,cast in enumerate(casts)]
    return repo,story,scenes


def head(repo,scene,name,ref):
    repo.set_head(scene.id,name,ref.id,repo.get_scene(scene.id).revision)


def context(repo,story,scene,stage):
    brief=repo.save_version(story.id,scene.id,'brief','{"objective":"Подія","beats":["Подія"]}',[])
    draft=repo.save_version(story.id,scene.id,'draft','Чернетка',[brief.id])
    head(repo,scene,'brief',brief);head(repo,scene,'draft',draft)
    if stage=='memory':
        head(repo,scene,'prose',repo.save_version(story.id,scene.id,'manual','Проза.',[]))
    return build_context(repo,scene.id,stage,settings(stage),editor_source_id=draft.id if stage=='rewrite' else None)


@pytest.mark.parametrize('stage',['brief','draft','rewrite'])
def test_block_present_for_writing_stages(tmp_path,stage):
    repo,story,(scene,)=prepared(tmp_path,[['A','B']],{'A':'Протагоністка','B':'Знайомий з: Анна'})
    text=context(repo,story,scene,stage).user_text
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — Анна' in text
    assert 'Знайомі: Богдан (до початку історії)' in text
    assert 'Ще не представлені' not in text


@pytest.mark.parametrize('stage',['edit','memory'])
def test_block_absent_for_edit_and_memory(tmp_path,stage):
    repo,story,(scene,)=prepared(tmp_path,[['A','B']],{'A':'Протагоністка'})
    view=repo.context_view(story.id)
    assert acquaintance_material(view,view.get_story(story.id),view.get_scene(scene.id),stage)==('',[])
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ' not in context(repo,story,scene,stage).user_text


def test_edit_stage_main_path_has_no_block(tmp_path):
    repo,story,(scene,)=prepared(tmp_path,[['A','B']],{'A':'Протагоністка'})
    brief=repo.save_version(story.id,scene.id,'brief','{"objective":"Подія","beats":["Подія"]}',[])
    draft=repo.save_version(story.id,scene.id,'draft','Чернетка',[brief.id])
    head(repo,scene,'brief',brief);head(repo,scene,'draft',draft)
    full=RoleSettings(provider=ProviderSettings(model='fake'),context_tokens=32768)
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ' not in build_context(repo,scene.id,'edit',full).user_text


def test_brief_block_lists_unintroduced_with_ids_and_field_instruction(tmp_path):
    repo,story,(scene,)=prepared(tmp_path,[['A','C']])
    text=context(repo,story,scene,'brief').user_text
    assert 'Ще не представлені: Віра [id=C]' in text and 'introduced' in text
    assert 'Знайомі:' not in text


@pytest.mark.parametrize('stage',['draft','rewrite'])
def test_other_stages_have_no_ids_and_no_field(tmp_path,stage):
    repo,story,(scene,)=prepared(tmp_path,[['A','C']])
    text=context(repo,story,scene,stage).user_text
    assert 'Ще не представлені: Віра' in text and '[id=' not in text and 'introduced' not in text


def test_no_block_when_hero_not_in_cast(tmp_path):
    repo,story,(scene,)=prepared(tmp_path,[['B','C']],{'A':'Протагоністка'})
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ' not in context(repo,story,scene,'brief').user_text


def test_no_block_when_only_hero_in_cast(tmp_path):
    repo,story,(scene,)=prepared(tmp_path,[['A']])
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ' not in context(repo,story,scene,'brief').user_text


def test_stale_lineage_brief_does_not_block_next_scene(tmp_path):
    repo,story,(s1,s2)=prepared(tmp_path,[['A','B'],['A','B']])
    seed=repo.save_version(story.id,s1.id,'manual','Джерело.',[])
    b=repo.save_version(story.id,s1.id,'brief',WritersBrief(objective='o',beats=['b'],introduced=['B']).model_dump_json(),[seed.id])
    d=repo.save_version(story.id,s1.id,'draft','Чернетка.',[b.id])
    e=repo.save_version(story.id,s1.id,'edited','Текст.',[d.id])
    head(repo,s1,'prose',e)
    m=repo.save_version(story.id,s1.id,'memory',MemorySnapshot(source_prose_ids=[e.id]).model_dump_json(),[])  # без ребра залежності: інвалідація брифа не чіпає пам’ять
    head(repo,s1,'memory',m)
    repo.invalidate_dependents([seed.id])
    assert repo.get_version(b.id).stale
    bundle=build_context(repo,s2.id,'brief',settings('brief'))
    assert b.id not in bundle.input_refs
    assert 'Знайомі: Богдан (зі сцени 1)' in bundle.user_text


def test_default_brief_prompt_is_v2_and_mentions_introduced():
    from storygen.generation.prompts import default_prompt
    assert 'introduced' in default_prompt('brief')
    assert 'introduced' not in default_prompt('draft')


def test_brief_run_warns_on_unexpected_introduced():
    from storygen.domain import Scene
    scene=Scene(id='s',story_id='t',title='С',position=0,character_ids=['A','B'])
    assert unexpected_introduced(scene,'A',['C'])
    assert unexpected_introduced(scene,'A',['A'])
    assert not unexpected_introduced(scene,'A',['B'])
    assert not unexpected_introduced(scene,'A',None)
    assert not unexpected_introduced(scene,'A',[])


@pytest.mark.parametrize('introduced,warned',[(['C'],True),(['B'],False)])
def test_brief_stage_records_planner_warning(tmp_path,introduced,warned):
    import threading
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    repo,story,(scene,)=prepared(tmp_path,[['A','B']])
    ctx=build_context(repo,scene.id,'brief',settings('brief'))
    body=WritersBrief(objective='o',beats=['b'],introduced=introduced).model_dump_json()
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=body)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'brief',ctx,Gateway(),threading.Event(),lambda _:None)
    warnings=attempt.context['planner_warnings']
    assert any('introduced містить ID поза складом' in w for w in warnings)==warned


def broken_anchor_story(tmp_path,casts):
    repo,story,scenes=prepared(tmp_path,casts)
    cards=[dict(schema_version=2,id='A',name='Анна',entries=[dict(id='eA',text='Протагоністка',availability='timeless',origin='author')]),
        dict(schema_version=2,id='B',name='Богдан',entries=[dict(id='eB',text='Опис',availability='timeless',origin='author')]),
        dict(schema_version=2,id='C',name='Віра',entries=[dict(id='eC',text='Знайомий з: Анна',availability='from_scene',available_from_scene_id='gone',origin='author')])]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    return repo,story,scenes


def test_broken_anchor_does_not_block_scene_without_hero(tmp_path):
    repo,story,(no_hero,with_hero)=broken_anchor_story(tmp_path,[['B'],['A','B']])
    assert 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ' not in context(repo,story,no_hero,'brief').user_text
    with pytest.raises(ValueError):context(repo,story,with_hero,'brief')


def test_planner_warning_survives_broken_anchor(tmp_path):
    import threading
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    repo,story,(scene,)=broken_anchor_story(tmp_path,[['B']])
    ctx=build_context(repo,scene.id,'brief',settings('brief'))
    body=WritersBrief(objective='o',beats=['b'],introduced=['C']).model_dump_json()
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=body)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'brief',ctx,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='completed'
    assert attempt.context['planner_warnings']
