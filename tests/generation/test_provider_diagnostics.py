import threading

import httpx

from storygen.domain import StoryCreate,SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.providers.streaming import build_generation_gateway
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage


def test_memory_provider_failure_is_durable_and_never_publishes(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Synthetic'))
    scene=repo.create_scene(story.id,SceneCreate(title='Scene'))
    prose=repo.save_version(story.id,scene.id,'manual','Synthetic evidence.',[])
    repo.set_head(scene.id,'prose',prose.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='synthetic'),context_tokens=8192,max_output_tokens=512)
    context=build_context(repo,scene.id,'memory',role)
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(401,json={'error':{'code':'invalid_api_key','message':'Synthetic authentication failure'}}))) as http:
        attempt=execute_stage(repo,scene.id,'memory',context,build_generation_gateway(role.provider,http),threading.Event(),lambda _:None)
    assert attempt.state=='failed' and attempt.result_version_id is None
    assert attempt.context['generation_failure']['category']=='authentication'
    assert attempt.context['generation_failure']['http_status']==401
    assert attempt.error.startswith('HTTP 401:')
    assert 'memory' not in repo.get_scene(scene.id).heads
    assert Repository(tmp_path).get_attempt(attempt.id).context['generation_failure']==attempt.context['generation_failure']
