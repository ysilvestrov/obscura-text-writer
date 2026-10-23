import json
import threading

import pytest

from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings,RoleSettings,ClassificationSettings
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.streaming import GenerationEvent
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from storygen.generation.copyedit_review import copyedit_preview,select_copyedits
from storygen.authoring.blueprints import save_role_settings


class Gateway:
    def __init__(self,text): self.text=text
    def stream(self,*_):
        yield GenerationEvent(type='delta',text=self.text)
        yield GenerationEvent(type='terminal',finish_reason='stop')


def fixture(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Тест'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft','Вона йшов.\n\nВона співаю.',[])
    repo.set_head(scene.id,'draft',draft.id,scene.revision)
    settings=RoleSettings(provider=ProviderSettings(model='writer-fake'),edit_mode='diff',classification=ClassificationSettings(provider=ProviderSettings(model='classifier-fake')))
    save_role_settings(repo,story.id,'editor',settings,repo.get_story(story.id).revision)
    a=execute_stage(repo,scene.id,'edit',build_context(repo,scene.id,'edit',settings),Gateway('Вона йшла.\n\nВона співає.'),threading.Event(),lambda _:None)
    return repo,scene,a


def test_queued_classification_preserves_proposal_and_head(tmp_path):
    repo,scene,a=fixture(tmp_path)
    before=copyedit_preview(repo,scene.id,a.id)
    payload={'changes':[dict(index=i,category='grammar',assessment='improvement',explanation='Узгодження.') for i in [0,1]]}
    called=[]
    def factory(provider):
        called.append(provider.model);return Gateway(json.dumps(payload))
    worker=RunCoordinator(repo,gateway_factory=factory)
    request=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=before['proposal_fingerprint'])
    run=worker.enqueue(request,'classify-one');run.state='running';repo.save_run(run);worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert called==['classifier-fake']
    after=copyedit_preview(repo,scene.id,a.id)
    assert after['classification']['changes']==payload['changes']
    assert after['proposal_fingerprint']==before['proposal_fingerprint']
    assert repo.get_attempt(a.id).state=='needs_review'
    assert not repo.get_scene(scene.id).heads.get('prose')
    assert after['classification_history'][0]['state']=='completed'


@pytest.mark.parametrize('indices',[[0],[0,0],[0,2]])
def test_bad_classifier_coverage_does_not_block_manual_review(tmp_path,indices):
    repo,scene,a=fixture(tmp_path);before=copyedit_preview(repo,scene.id,a.id)
    worker=RunCoordinator(repo,gateway_factory=lambda _:Gateway(json.dumps({'changes':[dict(index=i,category='grammar',assessment='improvement',explanation='Тест') for i in indices]})))
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=before['proposal_fingerprint'])
    run=worker.enqueue(req,'bad');run.state='running';repo.save_run(run);worker._execute(run.id)
    assert repo.get_run(run.id).state=='failed'
    after=copyedit_preview(repo,scene.id,a.id)
    assert after['classification'] is None
    assert after['can_apply']
    result=select_copyedits(repo,scene.id,a.id,[],after['expected_revision'],after['proposal_fingerprint'])
    assert repo.read_text(result['version'].id)=='Вона йшов.\n\nВона співаю.'


def test_classifier_rejects_forged_fingerprint_before_enqueue(tmp_path):
    repo,scene,a=fixture(tmp_path)
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint='forged')
    with pytest.raises(ValueError):RunCoordinator(repo).enqueue(req,'bad')


@pytest.mark.parametrize('reply',['I cannot classify this text.',"I'm sorry, but I cannot classify this text.",'Вибачте, я не можу класифікувати цей текст.'])
def test_refusal_blocks_same_classifier_for_story_but_not_selection(tmp_path,reply):
    repo,scene,a=fixture(tmp_path);before=copyedit_preview(repo,scene.id,a.id)
    worker=RunCoordinator(repo,gateway_factory=lambda _:Gateway(reply))
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=before['proposal_fingerprint'])
    run=worker.enqueue(req,'refusal');run.state='running';repo.save_run(run);worker._execute(run.id)
    after=copyedit_preview(repo,scene.id,a.id)
    assert after['can_apply'] and not after['can_classify']
    with pytest.raises(ValueError):worker.enqueue(req,'new-refusal')


def test_content_filter_terminal_blocks_classifier(tmp_path):
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    class FilteredGateway:
        def stream(self,*_):
            yield GenerationEvent(type='error',finish_reason='content_filter',message='Немає повної відповіді')
    worker=RunCoordinator(repo,gateway_factory=lambda _:FilteredGateway())
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    run=worker.enqueue(req,'filter');run.state='running';repo.save_run(run);worker._execute(run.id)
    saved=repo.list_attempts(scene.story_id,run.id)[0]
    assert saved.context['classification_failure']['category']=='refusal_content'
    assert not copyedit_preview(repo,scene.id,a.id)['can_classify']


def test_duplicate_classification_enqueue_is_idempotent_or_blocked(tmp_path):
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    worker=RunCoordinator(repo)
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    first=worker.enqueue(req,'one')
    assert worker.enqueue(req,'one').id==first.id
    with pytest.raises(ValueError):worker.enqueue(req,'two')


@pytest.mark.parametrize('category,blocked',[('timeout',False),('refusal_content',True)])
def test_gateway_failure_preserves_cause_and_only_refusal_blocks(tmp_path,category,blocked):
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    class FailedGateway:
        def stream(self,*_):
            yield GenerationEvent(type='error',message='Конкретна причина',failure={'category':category,'message':'Конкретна причина'})
    worker=RunCoordinator(repo,gateway_factory=lambda _:FailedGateway())
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    run=worker.enqueue(req,'failed');run.state='running';repo.save_run(run);worker._execute(run.id)
    saved=repo.list_attempts(scene.story_id,run.id)[0]
    assert saved.context['classification_failure']['category']==category
    assert saved.error=='Конкретна причина'
    assert copyedit_preview(repo,scene.id,a.id)['can_classify'] is not blocked


def test_length_retains_output_limit_category(tmp_path):
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    class LimitedGateway:
        def stream(self,*_):yield GenerationEvent(type='error',finish_reason='length',message='Вичерпано вихідний ліміт')
    worker=RunCoordinator(repo,gateway_factory=lambda _:LimitedGateway())
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    run=worker.enqueue(req,'limit');run.state='running';repo.save_run(run);worker._execute(run.id)
    assert repo.list_attempts(scene.story_id,run.id)[0].context['classification_failure']['category']=='output_limit'


def test_real_gateway_accounting_failure_is_budget_category():
    from types import SimpleNamespace
    from storygen.providers.streaming import OpenAIGenerationGateway
    gateway=OpenAIGenerationGateway(ProviderSettings(provider='venice',model='fake'))
    events=list(gateway.stream(SimpleNamespace(stage='classify'),threading.Event()))
    assert events[-1].failure['category']=='budget'


def test_classifier_pause_cancel_and_recovery_need_explicit_repeat(tmp_path):
    from storygen.domain import StageAttempt
    from storygen.generation.edit_classification import build_classification_context
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    worker=RunCoordinator(repo)
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    run=worker.enqueue(req,'lifecycle')
    assert worker.pause(run.id).state=='paused'
    assert worker.resume(run.id).state=='queued'
    run=repo.get_run(run.id);run.state='running';repo.save_run(run)
    ctx=build_classification_context(repo,req)
    repo.save_attempt(StageAttempt(id='interrupted-classifier',run_id=run.id,story_id=scene.story_id,scene_id=scene.id,stage='classify',partial_path=f'stories/{scene.story_id}/runs/interrupted-classifier/partial.txt',context={**ctx.model_dump(),'run_cursor':0}))
    worker.recover_interrupted()
    assert repo.get_run(run.id).state=='interrupted'
    with pytest.raises(ValueError):worker.resume(run.id)
    assert worker.resume(run.id,repeat_interrupted=True).state=='queued'
    assert worker.cancel(run.id).state=='cancelled'
    assert repo.get_attempt(a.id).state=='needs_review'


def test_zero_cloud_budget_stops_classifier_before_post(tmp_path,monkeypatch):
    import httpx
    from storygen.providers.streaming import OpenAIGenerationGateway
    from storygen.billing.service import set_limit
    from storygen.authoring.blueprints import get_role_settings
    repo,scene,a=fixture(tmp_path);p=copyedit_preview(repo,scene.id,a.id)
    role=get_role_settings(repo,scene.story_id)['editor']
    role.classification.provider=ProviderSettings(provider='venice',model='fake',response_mode='json_schema',key_env='TEST_CLASSIFIER_KEY')
    save_role_settings(repo,scene.story_id,'editor',role,repo.get_story(scene.story_id).revision)
    set_limit(repo,'story:'+scene.story_id,'0',0)
    monkeypatch.setenv('TEST_CLASSIFIER_KEY','test-only')
    sent=[]
    def handler(request):
        sent.append(request.method)
        assert request.method=='GET'
        return httpx.Response(200,json={'data':[{'id':'fake','object':'model','created':0,'owned_by':'test','model_spec':{'uncensored':True,'offline':False,'pricing':{'input':{'usd':1},'output':{'usd':2}},'capabilities':{'supportsResponseSchema':True}}}]})
    worker=RunCoordinator(repo,gateway_factory=lambda provider:OpenAIGenerationGateway(provider,http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    req=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='classify',proposal_attempt_id=a.id,proposal_fingerprint=p['proposal_fingerprint'])
    run=worker.enqueue(req,'no-money');run.state='running';repo.save_run(run);worker._execute(run.id)
    assert sent and 'POST' not in sent
    assert repo.list_attempts(scene.story_id,run.id)[0].context['classification_failure']['category']=='budget'
