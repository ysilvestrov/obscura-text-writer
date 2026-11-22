"""EDIT-LOOP-STOP-S05: a pass that returns an excerpt instead of the whole scene is a failed pass, not a candidate."""
import pytest

from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.worker import RunCoordinator
from storygen.generation.copyedit_review import copyedit_preview
from storygen.generation.editor_output import shrink_check,EditorShrinkError,editor_failure
from storygen.run_models import RunRequest

# Ten sentences, 50 words: 60% is 30 words.
SENTENCES=[f'Речення {i} має п’ять слів.' for i in range(10)]
SOURCE=' '.join(SENTENCES)
FIRST=SOURCE.replace('Речення 0 ','Речення нуль ')
EXCERPT=' '.join(SENTENCES[6:])  # 20 words, 40%


def seeded(tmp_path,responses,mode='diff',limit=5):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Уривок'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft',SOURCE,[])
    repo.set_head(scene.id,'draft',draft.id,scene.revision)
    save_role_settings(repo,story.id,'editor',RoleSettings(provider=ProviderSettings(model='synthetic'),edit_mode=mode),repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            yield GenerationEvent(type='delta',text=responses[len(calls)-1])
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='edit_loop',edit_pass_limit=limit),'loop')
    return repo,scene,draft,worker,run,calls


def test_message_names_counts_and_reference_without_text():
    with pytest.raises(EditorShrinkError) as caught:shrink_check(EXCERPT,SOURCE,SOURCE)
    failure=editor_failure(caught.value)
    assert failure['category']=='guard' and (failure['words_kept'],failure['words_total'])==(20,50)
    assert 'редактора: 20 із 50 (40%)' in failure['message'] and 'на вході проходу' in failure['message']
    assert 'Речення' not in failure['message'] and not failure['message'].endswith('.')
    shrink_check(' '.join(SOURCE.split()[:30]),SOURCE,SOURCE)  # exactly 60% is kept


def test_excerpt_after_success_offers_last_good_candidate(tmp_path):
    # diff and prose share save_pass_result; prose needs a brief, which this fixture does not build.
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[FIRST,EXCERPT,'ДОДАТКОВИЙ ВИКЛИК'])
    versions_before=len(repo.list_versions(scene.story_id,scene.id))
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==2
    assert current.editor_loop['stop_reason']=='pass_failed' and current.editor_loop['attempt_count']==2
    assert 'редактора: 20 із 50' in current.warning and 'Успішних проходів: 1' in current.warning
    assert copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])['preview']==FIRST
    failed=repo.list_attempts(scene.story_id,run.id)[1]
    assert failed.state=='failed' and failed.context['edit_loop_failure_origin']=='model_response'
    assert failed.context['editor_failure']['category']=='guard' and not failed.result_version_id
    assert all(repo.read_text(v.id)!=EXCERPT for v in repo.list_versions(scene.story_id,scene.id))
    assert len(repo.list_versions(scene.story_id,scene.id))==versions_before+2  # the loop's initial copy and the first candidate only
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


def test_excerpt_on_first_pass_fails_without_proposal_or_prose(tmp_path):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[EXCERPT,'ДОДАТКОВИЙ ВИКЛИК'])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='failed' and len(calls)==1 and 'редактора: 20 із 50' in current.error
    assert not current.editor_loop.get('proposal_attempt_id')
    assert repo.get_scene(scene.id).heads=={'draft':draft.id}


def test_gradual_erosion_is_checked_against_the_initial_copy(tmp_path):
    # 50 → 35 (70% of input) → 25: 71% of the pass input, but 50% of the initial copy.
    words=SOURCE.split()
    second,third=' '.join(words[:35]),' '.join(words[:25])
    repo,scene,_,worker,run,calls=seeded(tmp_path,[second,third])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and len(calls)==2
    assert 'редактора: 25 із 50' in current.warning and 'початкового тексту циклу' in current.warning
    assert copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])['preview']==second


def test_pass_just_above_threshold_is_a_candidate(tmp_path):
    kept=' '.join(SOURCE.split()[:31])
    repo,scene,_,worker,run,calls=seeded(tmp_path,[kept,kept])
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.editor_loop['stop_reason']=='no_changes' and current.state=='needs_review' and len(calls)==2
    assert copyedit_preview(repo,scene.id,current.editor_loop['proposal_attempt_id'])['preview']==kept


def test_rejected_pass_recovers_locally_without_another_call(tmp_path,monkeypatch):
    from storygen.generation import editor_loop
    repo,scene,_,worker,run,calls=seeded(tmp_path,[FIRST,EXCERPT,'ДОДАТКОВИЙ ВИКЛИК'])
    real=editor_loop.finish
    monkeypatch.setattr(editor_loop,'finish',lambda *args:(_ for _ in ()).throw(RuntimeError('checkpoint crash')))
    worker._execute(run.id)
    monkeypatch.setattr(editor_loop,'finish',real)
    interrupted=worker.get_run(run.id);interrupted.state='interrupted';repo.save_run(interrupted)
    assert editor_loop.readiness(repo,interrupted.request,interrupted)['calls']==0
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review' and len(calls)==2


@pytest.mark.parametrize('mode',['prose','diff'])
def test_remaining_workflow_stops_on_excerpt_before_memory(tmp_path,mode):
    import json
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Дві сцени'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {i}',beats=f'Подія {i}')) for i in range(2)]
    for name in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,name,RoleSettings(provider=ProviderSettings(model=name),edit_mode=mode,memory_mode='evidence_delta'),repo.get_story(story.id).revision)
    edits=['Олена тихо відчинила важкі двері номер нуль.','двері']
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            raw={'brief':json.dumps({'objective':'Сцена','beats':['Подія']}),'draft':'Олена тихо відчинив важкі двері номер нуль.'}.get(ctx.stage)
            if ctx.stage=='edit':raw=edits[sum(c.stage=='edit' for c in calls)-1]
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining',edit_workflow='loop',edit_pass_limit=3),'workflow')
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review',current.error
    checkpoint=current.editor_loops[str(current.cursor)]
    assert checkpoint['stop_reason']=='pass_failed' and 'редактора: 1 із 7' in current.warning
    assert copyedit_preview(repo,scenes[0].id,checkpoint['proposal_attempt_id'])['preview']==edits[0]
    assert [c.stage for c in calls]==['brief','draft','edit','edit'] and 'prose' not in repo.get_scene(scenes[0].id).heads
