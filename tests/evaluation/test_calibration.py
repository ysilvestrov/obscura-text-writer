from storygen.evaluation.calibration import calibrate, load_suite
from storygen.evaluation.models import EvaluationOutcome, EvidenceCheck, Finding
from storygen.evaluation.models import EvaluatorConfig, ScoringProfile
from storygen.evaluation.prompting import load_rubric
from storygen.evaluation.runner import evaluator_fingerprint, fingerprint_inputs


def report(case, good_report, finding=None, error=False, reverse=False):
    import uuid
    config, rubric, profile = EvaluatorConfig(provider="codex_cli",model="test",max_input_chars=30000), load_rubric(), ScoringProfile(version="candidate")
    if finding:
        good_report = good_report.model_copy(deep=True)
        good_report.findings = [finding]
    return EvaluationOutcome(status="error" if error else "incomplete", reasons=["api_failed"] if error else ["profile_uncalibrated"],
        report=None if error else good_report, evidence=EvidenceCheck(confirmed=[finding] if finding else []),
        fingerprint=fingerprint_inputs(case,rubric,profile,config,reverse),
        metadata={"case_id":case.id,"run_id":uuid.uuid4().hex,"reverse_pair":reverse,"preliminary_verdict":"failed" if finding else "passed",
            "evaluator_fingerprint":evaluator_fingerprint(config,rubric),
            "snapshots":{"case":case.model_dump(),"config":config.model_dump(),"rubric":rubric.model_dump(),"profile":profile.model_dump()}})


def test_calibration_counts_misses_false_positives_and_unavailable(sample_case, good_report):
    finding = Finding(criterion_id="ukrainian", severity="major", explanation="Помилка", suggestion="Виправити",
        citations=[dict(document_id="s1", document_version="1", quote="Олена відчинила двері бібліотеки.")])
    clean = sample_case.model_copy(update={"id":"clean"})
    unavailable = sample_case.model_copy(update={"id":"unavailable"})
    expected = {sample_case.id:{"findings":[{"criterion_id":"ukrainian","anchors":[{"document_id":"s1","quote":"Олена відчинила двері бібліотеки."}],"critical":True}]}, "clean":{"findings":[]},"unavailable":{"findings":[]}}
    result = calibrate([sample_case,clean,unavailable], expected, [report(sample_case,good_report,finding),report(clean,good_report,finding),report(unavailable,good_report,error=True)])
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["misses"] == 0
    assert result["available_runs"] == 2
    assert result["unavailable_runs"] == 1
    assert result["precision"] == 0.5
    assert result["eligible"] is False


def test_repeats_track_order_bias_and_score_spread(sample_case, good_report):
    a = report(sample_case, good_report)
    b = report(sample_case, good_report.model_copy(deep=True), reverse=True)
    b.report.assessments[0].score = 2
    b.metadata["preliminary_verdict"] = "failed"
    result = calibrate([sample_case], {sample_case.id:{"findings":[]}}, [a,b])
    assert result["stability"][sample_case.id]["score_ranges"]["ukrainian"] == 2
    assert result["stability"][sample_case.id]["verdict_changed"] is True


def test_fixture_suite_does_not_include_expected_answers():
    from pathlib import Path
    suite = load_suite(Path("tests/fixtures/evaluation/suite.json"))
    assert len(suite) >= 8
    assert all("expected" not in case.model_dump() for case in suite)


def test_calibration_cli_keeps_expected_answers_out_of_gateway(tmp_path, monkeypatch):
    import json
    from storygen.evaluation import cli
    from storygen.evaluation.models import GatewayResult, JudgeReport
    class Gateway:
        def complete(self, request):
            data = json.loads(request.messages[1]["content"])
            assert "findings" not in data
            assert "expectations" not in data
            report = JudgeReport(assessments=[dict(criterion_id=key,status="assessed",score=4,explanation="Контроль") for key in data["required_criteria"]],
                findings=[],checked_document_ids=[d["id"] for d in data["documents"]],limitations=[])
            return GatewayResult(text=report.model_dump_json(),finish_reason="stop")
    monkeypatch.setattr(cli, "build_gateway", lambda config:Gateway())
    code = cli.main(["calibrate","--suite","tests/fixtures/evaluation/suite.json","--config","config/evaluator.codex.json","--output",str(tmp_path),"--repeats","1"])
    assert code == 1
    metrics = json.loads((tmp_path/"calibration.json").read_text(encoding="utf-8"))
    assert metrics["misses"] == 7
    assert metrics["eligible"] is False


def test_calibration_rejects_changed_canon(sample_case, good_report):
    import pytest
    outcome = report(sample_case,good_report)
    sample_case.documents[0].text += " Новий канон."
    with pytest.raises(ValueError):
        calibrate([sample_case],{sample_case.id:{"findings":[]}},[outcome])


def test_calibration_rejects_mixed_evaluators_and_replayed_runs(sample_case, good_report):
    import pytest
    a,b = report(sample_case,good_report),report(sample_case,good_report)
    b.metadata["evaluator_fingerprint"] = "other-model-or-prompt"
    with pytest.raises(ValueError):
        calibrate([sample_case],{sample_case.id:{"findings":[]}},[a,b])
    with pytest.raises(ValueError):
        calibrate([sample_case],{sample_case.id:{"findings":[]}},[a,a,a],required_repeats=3)


def test_selected_subset_cannot_qualify_as_full_calibration(tmp_path, monkeypatch):
    import json
    from storygen.evaluation import cli
    from storygen.evaluation.models import GatewayResult, JudgeReport
    class Gateway:
        def complete(self, request):
            data = json.loads(request.messages[1]["content"])
            findings = []
            if data["id"] == "grammar":
                findings = [dict(criterion_id="ukrainian",severity="minor",explanation="Узгодження",suggestion="Виправити",citations=[dict(document_id="s1",document_version="1",quote="Олена відчинили двері бібліотеки.")])]
            report = JudgeReport(assessments=[dict(criterion_id=key,status="assessed",score=4,explanation="Контроль") for key in data["required_criteria"]],findings=findings,
                checked_document_ids=[d["id"] for d in data["documents"]],limitations=[])
            return GatewayResult(text=report.model_dump_json(),finish_reason="stop")
    cfg = tmp_path/"config.json"
    cfg.write_text(json.dumps(dict(provider="codex_cli",model="test",max_input_chars=30000)),encoding="utf-8")
    monkeypatch.setattr(cli,"build_gateway",lambda config:Gateway())
    code = cli.main(["calibrate","--suite","tests/fixtures/evaluation/suite.json","--config",str(cfg),"--case-id","clean","--case-id","grammar","--repeats","3","--output",str(tmp_path)])
    assert code == 1
    metrics = json.loads((tmp_path/"calibration.json").read_text(encoding="utf-8"))
    assert metrics["suite_complete"] is False


def test_preservation_and_canon_findings_are_both_valid(good_report):
    from pathlib import Path
    from storygen.evaluation.inputs import load_case, read_json
    case = load_case(Path("tests/fixtures/evaluation/revision_fact/case.json"))
    preservation = Finding(criterion_id="editorial_preservation",severity="major",explanation="Змінено вік",suggestion="Відновити",
        citations=[dict(document_id="s1",document_version="1",quote="Олені було сорок років."),dict(document_id="edited",document_version="1",quote="Олені було п’ятдесят років.")])
    fidelity = Finding(criterion_id="plan_fidelity",severity="major",explanation="Суперечність канону",suggestion="Відновити",
        citations=[dict(document_id="canon",document_version="1",quote="Олені сорок років."),dict(document_id="edited",document_version="1",quote="Олені було п’ятдесят років.")])
    outcome = report(case,good_report,preservation)
    outcome.evidence.confirmed.append(fidelity)
    outcome.report.findings.append(fidelity)
    expected = read_json(Path("tests/fixtures/evaluation/expectations.json"))
    result = calibrate([case],expected,[outcome])
    assert result["true_positives"] == 1
    assert result["false_positives"] == 0


def test_single_observation_does_not_claim_zero_variability(sample_case,good_report):
    result=calibrate([sample_case],{sample_case.id:{'findings':[]}},[report(sample_case,good_report)])
    assert result['stability'][sample_case.id]['score_ranges']['ukrainian'] is None


def test_packaged_calibration_suite_matches_test_control_materials():
    from pathlib import Path
    from storygen.evaluation.prompting import resource_text
    from storygen.evaluation.inputs import parse_json,read_json
    packaged=parse_json(resource_text('calibration_suite_v1.json'))
    assert packaged['cases']==[c.model_dump() for c in load_suite(Path('tests/fixtures/evaluation/suite.json'))]
    assert packaged['expectations']==read_json(Path('tests/fixtures/evaluation/expectations.json'))
