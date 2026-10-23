import json
import threading
import httpx
from storygen.providers.requests import generation_request, evaluation_request
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.evaluation.models import EvaluatorConfig, EvaluationRequest
from storygen.providers.streaming import build_generation_gateway
from storygen.generation.context import ContextBundle


def test_generation_exact_body_and_schema_in_preflight(tmp_path):
    role = RoleSettings(provider=ProviderSettings(model='m', response_mode='json_schema'))
    body = generation_request('brief', role, 'system', 'user', {})
    assert 'response_format' in body
    sent = []
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content='data: [DONE]\n\n')
    context = ContextBundle(story_id='s', scene_id='c', stage='brief', scene_revision=0, story_revision=0,
        settings=role, system_text='system', user_text='user', input_refs=[], fingerprint='f', estimated_tokens=1, api_request=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        list(build_generation_gateway(role.provider, http).stream(context, threading.Event()))
    assert sent == [body]


def test_evaluation_body_includes_provider_flags_and_schema():
    config = EvaluatorConfig(provider='venice', model='m', max_input_chars=10000, venice_disable_thinking=True)
    request = EvaluationRequest(messages=[{'role': 'user', 'content': 'text'}], response_schema={'type': 'object'},
        response_mode='json_schema', max_output_tokens=100, temperature=None)
    body = evaluation_request(config, request)
    assert body['response_format']['json_schema']['schema'] == request.response_schema
    assert body['venice_parameters']['disable_thinking'] is True
