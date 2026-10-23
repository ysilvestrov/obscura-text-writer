import json

from storygen.evaluation import cli
from storygen.evaluation.models import ScoringProfile
from storygen.evaluation.prompting import load_rubric
from storygen.evaluation.reports import compare_reports
from storygen.evaluation.runner import evaluate


def paths(tmp_path, sample_case):
    case = tmp_path / "сцена з пробілами.json"
    cfg = tmp_path / "config.json"
    case.write_text(sample_case.model_dump_json(), encoding="utf-8")
    cfg.write_text(json.dumps(dict(provider="codex_cli", model="test", max_input_chars=30000)), encoding="utf-8")
    return case, cfg


def test_dry_run_does_not_create_gateway(tmp_path, sample_case, monkeypatch, capsys):
    case, cfg = paths(tmp_path, sample_case)
    def prohibited(config):
        raise AssertionError("Не можна створювати клієнт у dry-run")
    monkeypatch.setattr(cli, "build_gateway", prohibited)
    assert cli.main(["evaluate", "--case", str(case), "--config", str(cfg), "--dry-run"]) == 0
    assert "codex_cli" in capsys.readouterr().out


def test_exit_codes_and_invalid_invocation(tmp_path, sample_case, monkeypatch, good_report):
    from storygen.evaluation.models import GatewayResult
    class Gateway:
        def complete(self, request):
            return GatewayResult(text=good_report.model_dump_json(), finish_reason="stop")
    monkeypatch.setattr(cli, "build_gateway", lambda config: Gateway())
    case, cfg = paths(tmp_path, sample_case)
    assert cli.main(["evaluate", "--case", str(case), "--config", str(cfg), "--output", str(tmp_path / "runs")]) == 2
    assert cli.main(["evaluate"]) == 3


def test_refusal_exit_code_is_distinct_and_calibration_stops(tmp_path, sample_case, monkeypatch):
    from storygen.evaluation.models import GatewayResult
    calls = []
    class Gateway:
        def complete(self, request):
            calls.append(request)
            return GatewayResult(text='', finish_reason='stop', refusal='Не можу оцінити.')
    monkeypatch.setattr(cli, 'build_gateway', lambda config: Gateway())
    case, cfg = paths(tmp_path, sample_case)
    assert cli.main(['evaluate', '--case', str(case), '--config', str(cfg), '--output', str(tmp_path / 'run')]) == 4
    calls.clear()
    assert cli.main(['calibrate', '--suite', 'src/storygen/evaluation/resources/calibration_suite_v2.json',
                     '--config', str(cfg), '--output', str(tmp_path / 'calibration')]) == 1
    assert len(calls) == 1
    metrics = json.loads((tmp_path / 'calibration' / 'calibration.json').read_text(encoding='utf-8'))
    assert metrics['refusal_count'] == 1 and metrics['eligible'] is False


def test_changed_canon_is_not_comparable(sample_case, good_report, calibrated_profile):
    from storygen.evaluation.models import EvaluationOutcome
    def outcome(canon):
        snapshot = sample_case.model_dump()
        snapshot["documents"][0]["text"] = canon
        return EvaluationOutcome(status="passed", report=good_report, metadata={"evaluator_fingerprint":"same", "snapshots":{"case":snapshot,"profile":calibrated_profile.model_dump()}})
    result = compare_reports(outcome("Канон один"), outcome("Канон інший"))
    assert result["status"] == "non_comparable"


def test_revision_regression_keeps_preservation_failures(sample_case, good_report, calibrated_profile):
    from storygen.evaluation.models import EvaluationOutcome
    metadata = {"evaluator_fingerprint":"same", "snapshots":{"case":sample_case.model_dump(),"profile":calibrated_profile.model_dump()}}
    base = EvaluationOutcome(status="passed", report=good_report.model_copy(deep=True), metadata=metadata)
    changed = base.model_copy(deep=True)
    changed.report.assessments[0].score = 2
    changed.status = "failed"
    result = compare_reports(base, changed)
    assert result["regression"] is True
    assert result["score_changes"]["ukrainian"] == -2
    changed.status = "incomplete"
    assert compare_reports(base, changed)["status"] == "non_comparable"


def test_cli_ukrainian_help_under_windows_legacy_encoding(tmp_path):
    import os
    import subprocess
    import sys
    env = dict(os.environ, PYTHONIOENCODING="cp1250")
    result = subprocess.run([sys.executable,"-m","storygen.evaluation.cli","--help"],cwd=tmp_path,env=env,capture_output=True)
    assert result.returncode == 0
    assert "української" in result.stdout.decode("utf-8")


def test_accounted_cli_respects_root_lock_and_dry_run(tmp_path,sample_case,monkeypatch):
    from storygen.storage.locking import AppInstanceLock
    case,cfg=paths(tmp_path,sample_case)
    class Gateway:
        def bind_accounting(self,value):raise AssertionError('locked before binding')
        def complete(self,request):raise AssertionError('no provider call')
    monkeypatch.setattr(cli,'build_gateway',lambda config:Gateway())
    data=tmp_path/'budget'
    args=['evaluate','--case',str(case),'--config',str(cfg),'--budget-data-dir',str(data)]
    assert cli.main(args+['--dry-run'])==0
    assert not data.exists()
    with AppInstanceLock(data):assert cli.main(args)==3
    assert not (data/'storygen.sqlite3').exists()
    with AppInstanceLock(data):pass
