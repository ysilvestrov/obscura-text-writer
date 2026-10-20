import httpx
import pytest

from storygen.domain import StoryCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.client import build_openai_client
from storygen.providers.discovery import discover_models
from storygen.authoring.blueprints import save_role_settings, get_role_settings


def test_four_roles_can_use_different_providers(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Ролі'))
    for role in ['planner','writer','editor','memory']:
        provider='openrouter' if role=='editor' else 'local'
        story=save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(provider=provider,model=role)),story.revision)
    assert get_role_settings(repo,story.id)['editor'].provider.provider=='openrouter'
    assert get_role_settings(repo,story.id)['writer'].provider.timeout==3600


def test_env_key_never_serialized(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','very-private-key')
    config=ProviderSettings(provider='openrouter',model='example/model')
    assert 'very-private-key' not in config.model_dump_json()
    client=build_openai_client(config)
    assert client.max_retries==0
    assert client.api_key=='very-private-key'
    assert config.timeout==180
    client.close()


def test_discovery_does_not_generate_or_load_by_request():
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'data':[{'id':'actual-model','object':'model','owned_by':'local'}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        models=discover_models(ProviderSettings(model='actual-model'),http_client=http)
    assert len(requests)==1 and requests[0].method=='GET'
    assert requests[0].url.path=='/v1/models'
    assert models[0].context_tokens is None


def test_local_url_and_secret_field_validation():
    with pytest.raises(ValueError): ProviderSettings(model='x',base_url='https://third-party.example/v1')
    with pytest.raises(ValueError): ProviderSettings(model='x',api_key='secret')
