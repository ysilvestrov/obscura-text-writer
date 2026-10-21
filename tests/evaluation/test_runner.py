import json

import pytest

from storygen.evaluation.models import EvaluatorConfig, GatewayResult, ScoringProfile
from storygen.evaluation.prompting import load_rubric
from storygen.evaluation.runner import evaluate, fingerprint_inputs


class StaticGateway:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        return GatewayResult(text=self.text, finish_reason="stop")


def config(**values):
    return EvaluatorConfig(provider="codex_cli", model="test-model", max_input_chars=30000, **values)


def test_run_preserves_inputs_raw_answer_and_status(sample_case, good_report, tmp_path):
    gateway = StaticGateway(good_report.model_dump_json())
    outcome = evaluate(sample_case, load_rubric(), ScoringProfile(version="candidate"), config(), gateway, tmp_path)
    assert outcome.status == "incomplete"
    assert outcome.metadata["preliminary_verdict"] == "passed"
    folder = tmp_path / outcome.metadata["run_id"]
    assert (folder / "raw_response.txt").read_text(encoding="utf-8") == good_report.model_dump_json()
    assert json.loads((folder / "inputs.json").read_text(encoding="utf-8"))["case"]["documents"][1]["text"] == sample_case.documents[1].text
    assert (folder / "report.md").is_file()
    assert json.loads((folder / "outcome.json").read_text(encoding="utf-8"))["status"] == "incomplete"
    second = evaluate(sample_case, load_rubric(), ScoringProfile(version="candidate"), config(), gateway, tmp_path)
    assert second.metadata["run_id"] != outcome.metadata["run_id"]


def test_fingerprint_changes_with_context_prompt_config_and_order(sample_case):
    rubric, profile = load_rubric(), ScoringProfile(version="candidate")
    original = fingerprint_inputs(sample_case, rubric, profile, config())
    sample_case.documents[0].text += " Зміна канону."
    assert fingerprint_inputs(sample_case, rubric, profile, config()) != original
    assert fingerprint_inputs(sample_case, rubric, profile, config(temperature=0)) != fingerprint_inputs(sample_case, rubric, profile, config())


def test_oversize_input_makes_no_request(sample_case, tmp_path):
    gateway = StaticGateway("{}")
    cfg = config().model_copy(update={"max_input_chars": 1})
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version="v"), cfg, gateway, tmp_path)
    assert result.status == "incomplete"
    assert gateway.calls == 0


@pytest.mark.parametrize("text", ['{} trailing', '{"a":1,"a":2}', '{"a":NaN}', '{}'])
def test_invalid_json_retained_as_error(sample_case, tmp_path, text):
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version="v"), config(), StaticGateway(text), tmp_path)
    assert result.status == "error"
    assert (tmp_path / result.metadata["run_id"] / "raw_response.txt").read_text(encoding="utf-8") == text


def test_refusal_is_not_story_failure(sample_case, tmp_path):
    class Refusing:
        def complete(self, request):
            return GatewayResult(text="", finish_reason="stop", refusal="Ні")
    result = evaluate(sample_case, load_rubric(), ScoringProfile(version="v"), config(), Refusing(), tmp_path)
    assert result.status == "refused"


def test_failed_write_never_marks_complete(sample_case, good_report, tmp_path, monkeypatch):
    from pathlib import Path
    original = Path.write_text
    def fail(self, *args, **kwargs):
        if self.name == "report.md":
            raise OSError("disk full")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail)
    with pytest.raises(OSError):
        evaluate(sample_case, load_rubric(), ScoringProfile(version="v"), config(), StaticGateway(good_report.model_dump_json()), tmp_path)
    assert not list(tmp_path.glob("*/outcome.json"))


def test_partial_api_reply_preserves_text_usage_and_error(sample_case, tmp_path):
    import httpx
    from storygen.evaluation.gateway import build_gateway
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json={"id":"partial","object":"chat.completion","created":0,"model":"test",
            "choices":[{"index":0,"finish_reason":"length","message":{"role":"assistant","content":"Незавершений звіт..."}}],
            "usage":{"prompt_tokens":20,"completion_tokens":10,"total_tokens":30}})
    cfg = EvaluatorConfig(provider="local",model="test",max_input_chars=30000)
    gateway = build_gateway(cfg,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    try:
        result = evaluate(sample_case,load_rubric(),ScoringProfile(version="v"),cfg,gateway,tmp_path)
    finally:
        gateway.close()
    assert result.status == "error"
    assert result.metadata["usage"]["total_tokens"] == 30
    assert (tmp_path/result.metadata["run_id"]/"raw_response.txt").read_text(encoding="utf-8") == "Незавершений звіт..."
    assert len(calls) == 1
