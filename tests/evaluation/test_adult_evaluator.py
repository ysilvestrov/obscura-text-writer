import json

import httpx
import pytest

from storygen.evaluation.gateway import build_gateway, GatewayFailure
from storygen.evaluation.models import EvaluatorConfig, GatewayResult, ScoringProfile
from storygen.evaluation.prompting import load_rubric
from storygen.evaluation.runner import evaluate


@pytest.mark.parametrize('kind', ['api', 'text', 'structured', 'content_filter'])
def test_explicit_refusal_has_no_literary_score(sample_case, tmp_path, kind):
    text = 'I cannot evaluate this content.'
    response = GatewayResult(text=text, finish_reason='stop', usage={'total_tokens': 17})
    if kind == 'api':
        response.refusal = 'Не можу оцінити цей текст.'
    elif kind == 'structured':
        response.text = json.dumps({'assessments': [], 'findings': [], 'checked_document_ids': [], 'limitations': [], 'refusal': 'Не оцінюю оголеність.'})
    elif kind == 'content_filter':
        response.finish_reason = 'content_filter'
    class Gateway:
        def complete(self, request):
            return response
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version='candidate'),
                      EvaluatorConfig(provider='local', model='offline', max_input_chars=30000), Gateway(), tmp_path)
    assert result.status == 'refused'
    assert result.report is None and 'preliminary_verdict' not in result.metadata
    assert result.metadata['usage']['total_tokens'] == 17
    assert result.failure.category in {'refusal_content', 'refusal_unknown'}
    assert (tmp_path / result.metadata['run_id'] / 'raw_response.txt').read_text(encoding='utf-8') == response.text


def test_refusal_phrase_inside_valid_report_is_not_refusal(sample_case, good_report, tmp_path):
    good_report.limitations = ['У цитаті персонаж каже: I cannot evaluate this content.']
    class Gateway:
        def complete(self, request):
            return GatewayResult(text=good_report.model_dump_json(), finish_reason='stop')
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version='candidate'),
                      EvaluatorConfig(provider='local', model='offline', max_input_chars=30000), Gateway(), tmp_path)
    assert result.status == 'incomplete' and result.report is not None


@pytest.mark.parametrize('text', ["I'm sorry, but I can't assist with evaluating explicit material.", 'Вибачте, я не можу оцінити цей текст.'])
def test_plain_refusal_with_apology_is_recognized(sample_case, tmp_path, text):
    class Gateway:
        def complete(self, request):
            return GatewayResult(text=text, finish_reason='stop')
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version='candidate'),
        EvaluatorConfig(provider='local', model='judge', max_input_chars=30000), Gateway(), tmp_path)
    assert result.status == 'refused'


def test_explicit_structured_refusal_discards_contradictory_scores(sample_case, good_report, tmp_path):
    payload = good_report.model_dump()
    payload['refusal'] = 'Не оцінюю оголеність.'
    class Gateway:
        def complete(self, request):
            return GatewayResult(text=json.dumps(payload), finish_reason='stop')
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version='candidate'),
        EvaluatorConfig(provider='local', model='judge', max_input_chars=30000), Gateway(), tmp_path)
    assert result.status == 'refused' and result.report is None


@pytest.mark.parametrize('eligible,schema', [(False, True), (True, False), (True, True)])
def test_venice_checks_catalog_before_sending_documents(monkeypatch, eligible, schema):
    monkeypatch.setenv('VENICE_API_KEY', 'r04-test-key')
    seen = []
    def handle(req):
        seen.append(req)
        if req.url.path.endswith('/models'):
            return httpx.Response(200, json={'object': 'list', 'data': [{'id': 'judge', 'object': 'model', 'created': 0,
                'owned_by': 'venice', 'model_spec': {'uncensored': eligible, 'capabilities': {'supportsResponseSchema': schema}}}]})
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'judge',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{}'}}]})
    from storygen.evaluation.models import EvaluationRequest
    request = EvaluationRequest(messages=[{'role': 'user', 'content': 'Незмінений авторський текст'}],
        response_schema={'type': 'object'}, response_mode='json_schema', max_output_tokens=100, temperature=None)
    config = EvaluatorConfig(provider='venice', model='judge', max_input_chars=30000)
    gateway = build_gateway(config, http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    try:
        if eligible and schema:
            gateway.complete(request)
            body = json.loads(seen[-1].content)
            assert body['messages'] == request.messages
            assert body['venice_parameters']['enable_web_search'] == 'off'
            assert body['venice_parameters']['include_venice_system_prompt'] is False
            assert str(seen[-1].url) == 'https://api.venice.ai/api/v1/chat/completions'
        else:
            with pytest.raises(GatewayFailure):
                gateway.complete(request)
            assert len(seen) == 1
    finally:
        gateway.close()


@pytest.mark.parametrize('status,code,category', [(401, 'invalid_api_key', 'authentication'),
    (429, 'insufficient_quota', 'quota'), (429, 'rate_limit_exceeded', 'rate_limit'), (400, 'content_filter', 'refusal_content')])
def test_provider_failure_keeps_real_cause_without_secrets(monkeypatch, status, code, category):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'r04-private-key')
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(status, headers={'x-request-id': 'request-42'},
            json={'error': {'code': code, 'type': code, 'message': 'Причина: ' + code + ' Bearer r04-private-key'}})
    from storygen.evaluation.models import EvaluationRequest
    gateway = build_gateway(EvaluatorConfig(provider='openrouter', base_url='https://openrouter.ai/api/v1', model='judge', max_input_chars=30000),
                            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    try:
        with pytest.raises(GatewayFailure) as caught:
            gateway.complete(EvaluationRequest(messages=[{'role': 'user', 'content': 'Текст'}], response_schema={}, response_mode='prompt_json', max_output_tokens=50, temperature=None))
        detail = caught.value.detail
        assert detail.category == category
        assert detail.http_status == status and detail.provider_code == code
        assert detail.request_id == 'request-42'
        assert code in detail.provider_message
        assert 'r04-private-key' not in detail.model_dump_json()
        assert len(calls) == 1
    finally:
        gateway.close()
