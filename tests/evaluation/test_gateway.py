import json
import subprocess

import httpx
import pytest

from storygen.evaluation.models import EvaluatorConfig, EvaluationRequest
from storygen.evaluation.gateway import GatewayFailure, build_gateway
from storygen.evaluation.codex_gateway import CodexGateway


def request(mode="json_schema"):
    return EvaluationRequest(messages=[{"role":"system","content":"Оціни текст"},{"role":"user","content":"Олена відчинила двері."}],
        response_schema={"type":"object","properties":{},"additionalProperties":False}, response_mode=mode, max_output_tokens=100, temperature=None)


def completion(content="{}", reason="stop", refusal=None):
    return {"id":"chat-test", "object":"chat.completion", "created":0, "model":"test", "choices":[{"index":0,"finish_reason":reason,"message":{"role":"assistant","content":content,"refusal":refusal}}]}


@pytest.mark.parametrize("provider,base", [("local","http://localhost:1235/v1"),("openrouter","https://openrouter.ai/api/v1")])
def test_request_url_model_schema_and_optional_usage(provider, base, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-not-output")
    seen = []
    def handle(req):
        seen.append(req)
        return httpx.Response(200, json=completion())
    config = EvaluatorConfig(provider=provider, base_url=base, model="exact/model", max_input_chars=30000)
    gateway = build_gateway(config, http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    result = gateway.complete(request())
    assert len(seen) == 1
    assert str(seen[0].url) == base + "/chat/completions"
    body = json.loads(seen[0].content)
    assert body["model"] == "exact/model"
    assert body["response_format"]["type"] == "json_schema"
    assert "temperature" not in body
    assert ("provider" in body) == (provider == "openrouter")
    assert result.usage == {}
    assert "test-secret-not-output" not in config.model_dump_json()
    gateway.close()


@pytest.mark.parametrize("kind", ["timeout", "429", "length", "refusal", "empty"])
def test_single_attempt_on_timeout_429_and_partial_completion(kind):
    seen = []
    def handle(req):
        seen.append(req)
        if kind == "timeout":
            raise httpx.ReadTimeout("secret hidden", request=req)
        if kind == "429":
            return httpx.Response(429, json={"error":{"message":"secret hidden"}})
        return httpx.Response(200, json=completion(content="" if kind == "empty" else "{}", reason="length" if kind == "length" else "stop", refusal="Відмова" if kind == "refusal" else None))
    gateway = build_gateway(EvaluatorConfig(provider="local", model="test", max_input_chars=30000), http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    with pytest.raises(GatewayFailure) as caught:
        gateway.complete(request())
    assert len(seen) == 1
    assert "secret hidden" not in str(caught.value)
    gateway.close()


def test_prompt_json_does_not_send_schema():
    def handle(req):
        assert "response_format" not in json.loads(req.content)
        return httpx.Response(200, json=completion())
    gateway = build_gateway(EvaluatorConfig(provider="local", model="test", max_input_chars=30000), http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    assert gateway.complete(request("prompt_json")).text == "{}"
    gateway.close()


def test_codex_cli_uses_stdin_schema_readonly_and_no_shell(tmp_path):
    seen = []
    def run(args, **kwargs):
        seen.append((args, kwargs))
        assert kwargs["shell"] is False
        assert "Олена" in kwargs["input"]
        assert args[args.index("--sandbox") + 1] == "read-only"
        from pathlib import Path
        Path(args[args.index("--output-last-message") + 1]).write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout='{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n', stderr="")
    gateway = CodexGateway(EvaluatorConfig(provider="codex_cli", max_input_chars=30000), run=run, temp_root=tmp_path)
    result = gateway.complete(request())
    assert result.text == "{}"
    assert result.usage["input_tokens"] == 10
    assert len(seen) == 1


def test_codex_failure_is_sanitized_and_not_retried(tmp_path):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="secret hidden")
    gateway = CodexGateway(EvaluatorConfig(provider="codex_cli", max_input_chars=30000), run=run, temp_root=tmp_path)
    with pytest.raises(GatewayFailure, match="codex_failed") as caught:
        gateway.complete(request())
    assert "secret hidden" not in str(caught.value)


def test_codex_timeout_and_structured_error_keep_cause(tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('codex', 1)
    config = EvaluatorConfig(provider='codex_cli', model='judge', max_input_chars=30000)
    with pytest.raises(GatewayFailure) as caught:
        CodexGateway(config, run=timeout, temp_root=tmp_path).complete(request())
    assert caught.value.detail.category == 'timeout'
    def denied(*args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout=json.dumps({'type': 'turn.failed', 'error': {'code': 'insufficient_quota', 'message': 'Quota exceeded'}}), stderr='private stderr')
    with pytest.raises(GatewayFailure) as caught:
        CodexGateway(config, run=denied, temp_root=tmp_path).complete(request())
    assert caught.value.detail.category == 'quota'
    assert caught.value.detail.provider_code == 'insufficient_quota'
    assert 'private stderr' not in caught.value.detail.model_dump_json()
