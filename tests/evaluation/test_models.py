import json

import pytest
from pydantic import ValidationError

from storygen.evaluation.models import CriterionAssessment, EvaluationCase, EvaluatorConfig
from storygen.evaluation.inputs import load_case


@pytest.mark.parametrize("score", ["4", True, -1, 5])
def test_score_requires_strict_integer(score):
    with pytest.raises(ValidationError):
        CriterionAssessment(criterion_id="ukrainian", status="assessed", score=score, explanation="Перевірено")


@pytest.mark.parametrize("status,score", [("assessed", None), ("not_checked", 4), ("not_applicable", 0)])
def test_status_score_consistency(status, score):
    with pytest.raises(ValidationError):
        CriterionAssessment(criterion_id="ukrainian", status=status, score=score, explanation="Причина")


def test_duplicate_ids_rejected():
    doc = dict(id="s1", version="1", kind="scene", text="Олена відчинила двері бібліотеки.")
    with pytest.raises(ValidationError):
        EvaluationCase(id="sample", mode="scene", documents=[doc, doc], target_ids=["s1"])


def test_unknown_target_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase(id="sample", mode="scene", documents=[], target_ids=["missing"])


def test_utf8_bom_and_relative_paths(tmp_path):
    (tmp_path / "сцена.txt").write_text("Олена відчинила двері бібліотеки.", encoding="utf-8-sig")
    manifest = dict(id="sample", mode="scene", documents=[dict(id="s1", version="1", kind="scene", path="сцена.txt")], target_ids=["s1"])
    (tmp_path / "case.json").write_text(json.dumps(manifest), encoding="utf-8-sig")
    assert load_case(tmp_path / "case.json").documents[0].text == "Олена відчинила двері бібліотеки."


@pytest.mark.parametrize("path", ["../outside.txt", "C:/outside.txt", "missing.txt"])
def test_paths_stay_under_case_directory(tmp_path, path):
    manifest = dict(id="sample", mode="scene", documents=[dict(id="s1", version="1", kind="scene", path=path)], target_ids=["s1"])
    (tmp_path / "case.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        load_case(tmp_path / "case.json")


def test_config_rejects_empty_model_and_wrong_cloud_host():
    for overrides in [dict(model=" "), dict(base_url="https://example.com/v1")]:
        values = dict(provider="openrouter", model="example/model", base_url="https://openrouter.ai/api/v1", max_input_chars=10000)
        values.update(overrides)
        with pytest.raises(ValidationError):
            EvaluatorConfig(**values)
