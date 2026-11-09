import socket
import threading

import pytest

from storygen.evaluation.models import EvaluationCase, JudgeReport, ScoringProfile


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    local=threading.local()
    socketpair=socket.socketpair
    def internal_pair(*args,**kwargs):
        local.in_pair=True
        try:
            return socketpair(*args,**kwargs)
        finally:
            local.in_pair=False
    def guard(original):
        def checked(*args,**kwargs):
            if getattr(local,"in_pair",False):
                return original(*args,**kwargs)
            raise AssertionError("Тест не повинен звертатися до мережі")
        return checked
    monkeypatch.setattr(socket,"socketpair",internal_pair)
    monkeypatch.setattr(socket.socket,"connect",guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket,"connect_ex",guard(socket.socket.connect_ex))


def pytest_configure(config):
    config.addinivalue_line("markers","unrated_stories: нові твори в тесті створюються без вікового рейтингу (як у застосунку)")


@pytest.fixture(autouse=True)
def rated_stories_by_default(request,monkeypatch):
    """Generation is blocked for unrated stories, so test stories start rated R(0,0,0).

    The application itself creates stories unrated; tests of that behaviour opt out with
    ``@pytest.mark.unrated_stories``. The guard is never weakened.
    """
    if request.node.get_closest_marker("unrated_stories"):
        return
    from storygen.domain import ContentRating
    from storygen.storage.repository import Repository
    original=Repository.create_story
    def create_story(self,data):
        story=original(self,data)
        if story.content_rating is None:
            rating=ContentRating(sexual=0,violence=0,themes=0)
            story=story.model_copy(update={"content_rating":rating,"initial_content_rating":rating})
            with self.db.connection() as db:
                db.execute("UPDATE stories SET payload=? WHERE id=?",(story.model_dump_json(),story.id))
        return story
    monkeypatch.setattr(Repository,"create_story",create_story)


@pytest.fixture
def sample_case():
    return EvaluationCase(id="sample", mode="scene", documents=[
        dict(id="canon", version="1", kind="canon", text="Олена має сорок років. Вона бібліотекарка."),
        dict(id="s1", version="1", kind="scene", text="Олена відчинила двері бібліотеки. Їй було сорок років."),
    ], target_ids=["s1"])


@pytest.fixture
def accounted_call(tmp_path):
    """Real isolated ledger for mocked cloud transports; never a budget bypass."""
    from datetime import timedelta
    from uuid import uuid4
    from storygen.storage.repository import Repository
    from storygen.billing.models import Tariff, utcnow
    from storygen.billing.service import set_limit, save_tariff
    from storygen.providers.accounting import CallAccounting
    repo=Repository(tmp_path/'accounting')
    set_limit(repo,'cli:mock','1000',0)
    def create(provider,model):
        endpoint={'venice':'https://api.venice.ai/api/v1','openrouter':'https://openrouter.ai/api/v1'}[provider]
        save_tariff(repo,Tariff(provider=provider,model=model,base_url=endpoint,input_per_million='1',output_per_million='2',
            source='mock provider tariff',kind='manual',expires_at=(utcnow()+timedelta(days=1)).isoformat()))
        return CallAccounting(repo,'cli:mock','mock-run',uuid4().hex)
    return create


@pytest.fixture
def good_report():
    return JudgeReport(assessments=[dict(criterion_id=key, status="assessed", score=4, explanation="Проблем не виявлено.")
        for key in ["ukrainian", "style", "voice", "plan_fidelity"]], findings=[], checked_document_ids=["canon", "s1"], limitations=[])


@pytest.fixture
def calibrated_profile():
    return ScoringProfile(version="test-v1", calibrated=True, evaluator_fingerprint="test", calibration_fingerprint="test")


@pytest.fixture
def rewrite_case(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.storage.repository import Repository
    from storygen.authoring.comments import CommentPayload, comment_fingerprint
    from storygen.providers.models import ProviderSettings, RoleSettings
    from storygen.authoring.blueprints import save_role_settings
    from storygen.run_models import RunRequest
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Нейтральний тест'))
    scene=repo.create_scene(story.id,SceneCreate(title='Парк',beats='Прогулянка парком.'))
    source=repo.save_version(story.id,scene.id,'draft','Вечір був **тихим**. Вона йшла додому.',[],content_format='markdown')
    repo.set_head(scene.id,'draft',source.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='fake-writer',response_mode='json_schema'),context_tokens=32768,max_output_tokens=4096)
    save_role_settings(repo,story.id,'writer',role,repo.get_story(story.id).revision)
    scene=repo.get_scene(scene.id)
    saved=repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',scene.revision,0,
        CommentPayload(general='Зробити лаконічніше.',comments=[dict(id='note1',instruction='Додати емоцій.',anchor=dict(start=0,end=5,source_quote='Вечір',display_quote='Вечір'))]),expected_source_version_id=source.id)
    notes=saved['comment_set']
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='rewrite',source_version_id=source.id,comment_set_id=notes.id,comment_fingerprint=comment_fingerprint(notes,source))
    return repo,scene,source,notes,role,request


@pytest.fixture
def rewrite_proposal(rewrite_case):
    import threading
    from storygen.generation.assisted_writing import build_rewrite_context
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    repo,scene,source,notes,role,request=rewrite_case
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text='Вечір був **світлим**. Вона поспішала додому.')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'rewrite',build_rewrite_context(repo,request),Gateway(),threading.Event(),lambda _:None)
    return repo,scene,source,notes,attempt
