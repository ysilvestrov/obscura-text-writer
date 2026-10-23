import httpx
import pytest
from storygen.evaluation.gateway import OpenAICompatibleGateway, GatewayFailure
from storygen.evaluation.models import EvaluatorConfig, EvaluationRequest


def test_cloud_gateway_without_scope_never_posts(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    requests = []
    with httpx.Client(transport=httpx.MockTransport(lambda r: requests.append(r) or httpx.Response(500))) as client:
        gateway = OpenAICompatibleGateway(EvaluatorConfig(provider='openrouter', model='m', max_input_chars=10000), http_client=client)
        with pytest.raises(GatewayFailure, match='бюджетного scope'):
            gateway.complete(EvaluationRequest(messages=[{'role': 'user', 'content': 'text'}], response_schema={},
                response_mode='prompt_json', temperature=None, max_output_tokens=10))
    assert not requests
