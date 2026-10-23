import json
import threading
import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.run_models import RunRequest
from storygen.generation.worker import RunCoordinator
from storygen.generation.context import ContextOverflow
from storygen.generation.publication_metadata import build_publication_context, suggestions_state
from storygen.publication_suggestions import parse_suggestions


class Gateway:
    def __init__(self,text):self.text=text
    def stream(self,*args):
        yield GenerationEvent(type='delta',text=self.text)
        yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':123,'completion_tokens':50})


def seeded(root,scenes=2):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Назва'))
    role=RoleSettings(provider=ProviderSettings(model='planner-test',response_mode='json_schema'),context_tokens=128000,max_input_chars=1000000,max_output_tokens=2048)
    save_role_settings(repo,story.id,'planner',role,story.revision)
    for i in range(scenes):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Частина {i+1}',beats='SECRET PLAN'))
        save_manual_prose(repo,scene.id,f'Готова проза сцени {i+1}. Літо й місто.',0)
    return repo,story


def run_proposal(repo,story,reply=None,gateway=None):
    payload={'title':None,'annotation':'Коротка анотація.','genres':['short_story'],'keywords':['літо']}
    worker=RunCoordinator(repo,gateway_factory=lambda _:gateway or Gateway(json.dumps(reply or payload,ensure_ascii=False)))
    request=RunRequest(story_id=story.id,mode='publication_suggest')
    run=worker.enqueue(request,'suggest-one');run.state='running';repo.save_run(run);worker._execute(run.id)
    return worker,repo.get_run(run.id)


def test_full_text_seven_scenes_dedicated_prompt_and_schema(tmp_path):
    repo,story=seeded(tmp_path,7)
    context=build_publication_context(repo,story.id)
    assert 'SECRET PLAN' not in context.user_text
    for i in range(7):assert f'Готова проза сцени {i+1}.' in context.user_text
    assert context.settings.provider.model=='planner-test' and len(context.input_refs)==7
    assert context.api_request['response_format']['json_schema']['name']=='publication_suggest'
    assert json.loads(context.fragments['publication_eligible'])==['annotation','genres','keywords']
    before=repo.publication('get_card',story_id=story.id)
    worker,run=run_proposal(repo,story)
    assert run.state=='completed'
    assert repo.publication('get_card',story_id=story.id)==before
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.result_version_id is None and attempt.context['publication_proposal']
    assert suggestions_state(repo,story.id)['proposals'][0]['can_apply']
    assert worker.enqueue(run.request,'suggest-one').id==run.id


def test_no_dispatch_or_run_on_context_overflow_or_full_card(tmp_path):
    repo,story=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='small'),context_tokens=1024,max_output_tokens=512,max_input_chars=50)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    with pytest.raises(ContextOverflow):build_publication_context(repo,story.id)
    called=[];worker=RunCoordinator(repo,gateway_factory=lambda p:called.append(p))
    with pytest.raises(ValueError,match='Контекст'):worker.enqueue(RunRequest(story_id=story.id,mode='publication_suggest'),'overflow')
    assert not called and not repo.list_runs(story.id) and not repo.list_attempts(story.id)
    repo.publication('save_card',story_id=story.id,data=PublicationData(annotation='Авторська',genres=['short_story'],keywords=['тег']),expected_revision=0,expected_signature_revisions={})
    with pytest.raises(ValueError,match='порожніх'):build_publication_context(repo,story.id)


@pytest.mark.parametrize('text',[
    '{}','{"annotation":"А","annotation":"Б"}',
    '{"annotation":"Текст","publisher":"Вигаданий"}',
    '{"annotation":"Текст","genres":["unknown"]}',
    '{"title":"Переписана назва"}',
    '{"annotation":"","genres":[],"keywords":[]}',
    '{"annotation":NaN}',
])
def test_invalid_suggestions_are_rejected(text):
    with pytest.raises(ValueError):parse_suggestions(text,['annotation','genres','keywords'])


@pytest.mark.parametrize('empty', [{'genres':[]}, {'annotation':'   '}, {'keywords':[]}, {'genres':None}])
def test_partial_suggestions_skip_only_empty_fields(empty):
    payload={'annotation':'Анотація','genres':['short_story'],'keywords':['літо'],**empty}
    warnings=[]
    result=parse_suggestions(json.dumps(payload),['annotation','genres','keywords'],warnings)
    assert set(result)==set(payload)-set(empty)
    assert len(warnings)==1 and next(iter(empty)) in warnings[0]


@pytest.mark.parametrize('existing_genre',[False,True])
def test_partial_suggestions_preserve_review_and_warning_without_card_write(tmp_path,existing_genre):
    repo,story=seeded(tmp_path)
    genres=['short_story'] if existing_genre else []
    if existing_genre:
        repo.publication('save_card',story_id=story.id,data=PublicationData(genres=genres),expected_revision=0,expected_signature_revisions={})
    before=repo.publication('get_card',story_id=story.id)
    _,run=run_proposal(repo,story,reply={'annotation':'Анотація','genres':[],'keywords':['літо']})
    assert run.state=='completed' and 'genres' in run.warning
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.context['publication_proposal']['suggestions']=={'annotation':'Анотація','keywords':['літо']}
    assert attempt.context['publication_warnings']
    result=suggestions_state(repo,story.id)
    assert result['proposals'][0]['can_apply']
    assert result['proposals'][0]['warnings']==attempt.context['publication_warnings']
    assert result['history'][0]['warnings']==attempt.context['publication_warnings']
    assert repo.publication('get_card',story_id=story.id)==before
    proposal=result['proposals'][0]
    saved=repo.publication('save_card',story_id=story.id,data=PublicationData(annotation='Авторська анотація',keywords=['літо'],genres=genres),expected_revision=before.card.revision,expected_signature_revisions={},suggestion={'attempt_id':attempt.id,'fingerprint':proposal['fingerprint'],'fields':['annotation','keywords']})
    assert saved.card.annotation=='Авторська анотація' and saved.card.genres==genres


@pytest.mark.parametrize('payload',[{}, {'genres':None}, {'annotation':'  ','genres':[],'keywords':[]}])
def test_no_nonempty_suggestion_has_specific_error(payload):
    with pytest.raises(ValueError,match='жодного непорожнього'):
        parse_suggestions(json.dumps(payload),['annotation','genres','keywords'])


def test_empty_unrequested_known_field_is_ignored_with_warning():
    warnings=[]
    result=parse_suggestions('{"annotation":"Анотація","genres":[],"keywords":["літо"]}',['annotation','keywords'],warnings)
    assert result=={'annotation':'Анотація','keywords':['літо']}
    assert len(warnings)==1 and 'genres' in warnings[0] and 'не змінено' in warnings[0]
    for field,value in [('genres',['short_story']),('publisher',''),('unknown',[])]:
        with pytest.raises(ValueError):
            parse_suggestions(json.dumps({'annotation':'Анотація',field:value}),['annotation','keywords'])


@pytest.mark.parametrize('kind',['empty','length','refusal_content','timeout','protocol'])
def test_failed_attempt_preserves_real_cause_without_card_write(tmp_path,kind):
    repo,story=seeded(tmp_path)
    class Failed:
        def stream(self,*args):
            if kind=='protocol':yield GenerationEvent(type='delta',text='not JSON')
            if kind in {'empty','protocol'}:yield GenerationEvent(type='terminal',finish_reason='stop')
            else:yield GenerationEvent(type='error',finish_reason='length' if kind=='length' else None,message='Реальна причина',failure={'category':kind,'message':'Реальна причина'})
    _,run=run_proposal(repo,story,gateway=Failed())
    assert run.state=='failed'
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.context['publication_failure']['category']=={'empty':'empty_output','length':'output_limit'}.get(kind,kind)
    assert repo.publication('get_card',story_id=story.id).card.revision==0
    assert not suggestions_state(repo,story.id)['proposals']


def test_duplicate_active_and_cancel_recovery_no_automatic_retry(tmp_path):
    repo,story=seeded(tmp_path);worker=RunCoordinator(repo)
    request=RunRequest(story_id=story.id,mode='publication_suggest')
    run=worker.enqueue(request,'one')
    assert worker.enqueue(request,'one').id==run.id
    with pytest.raises(ValueError):worker.enqueue(request,'two')
    cancelled=worker.cancel(run.id)
    assert cancelled.state=='cancelled'
    new=worker.enqueue(request,'three');new.state='running';repo.save_run(new)
    worker.recover_interrupted()
    assert repo.get_run(new.id).state=='interrupted'


@pytest.mark.parametrize('text,category',[
    ('I cannot assist with this request.','refusal_unknown'),
    ('Я не можу створити анотацію через сексуальний контент.','refusal_content'),
    ('I cannot generate metadata for sexually explicit content.','refusal_content'),
])
def test_text_refusal_cannot_be_accepted(tmp_path,text,category):
    repo,story=seeded(tmp_path)
    _,run=run_proposal(repo,story,gateway=Gateway(text))
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.context['publication_failure']['category']==category


def test_paid_preflight_requires_explicit_story_limit(tmp_path):
    repo,story=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(provider='venice',model='paid'),context_tokens=128000,max_input_chars=1000000,max_output_tokens=2048)
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    called=[];worker=RunCoordinator(repo,gateway_factory=lambda p:called.append(p))
    with pytest.raises(ValueError,match='бюджету'):
        worker.enqueue(RunRequest(story_id=story.id,mode='publication_suggest'),'paid')
    assert not called and not repo.list_runs(story.id)


def test_cancel_during_stream_preserves_partial_without_proposal(tmp_path):
    repo,story=seeded(tmp_path)
    class Cancelled:
        def stream(self,context,cancel):
            yield GenerationEvent(type='delta',text='Часткова відповідь')
            cancel.set()
            yield GenerationEvent(type='cancelled',usage={'completion_tokens':3})
    _,run=run_proposal(repo,story,gateway=Cancelled())
    assert run.state=='cancelled'
    attempt=repo.list_attempts(story.id,run.id)[0]
    assert attempt.state=='cancelled' and attempt.usage['completion_tokens']==3
    assert repo.files.read_partial(attempt.partial_path)=='Часткова відповідь'
    assert not suggestions_state(repo,story.id)['proposals']
