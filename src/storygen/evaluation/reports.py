import json
from pathlib import Path

from .models import EvaluationOutcome


def write_reports(outcome: EvaluationOutcome, output_dir: Path) -> Path:
    folder = output_dir / outcome.metadata["run_id"]
    folder.mkdir(parents=True, exist_ok=False)
    snapshots = outcome.metadata["snapshots"]
    (folder / "inputs.json").write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "raw_response.txt").write_text(outcome.metadata.get("raw_response", ""), encoding="utf-8")
    (folder / "request.json").write_text(json.dumps(outcome.metadata["request"], ensure_ascii=False, indent=2), encoding="utf-8")
    labels = {"passed":"Пройдено", "failed":"Не пройдено", "incomplete":"Оцінювання неповне", "error":"Помилка оцінювання", 'refused': 'Відмова оцінювача'}
    lines = ["# Звіт оцінювання", "", f"Статус: {labels[outcome.status]}", "", f"Fingerprint: `{outcome.fingerprint}`", ""]
    if outcome.reasons:
        lines += ["Причини:", ""] + [f"- {reason}" for reason in outcome.reasons] + [""]
    if outcome.failure:
        lines += ['Діагностика:', '', outcome.failure.model_dump_json(indent=2), '']
    if outcome.report:
        lines += ["| Критерій | Бал | Статус |", "|---|---:|---|"]
        lines += [f"| {a.criterion_id} | {a.score if a.score is not None else '—'} | {a.status} |" for a in outcome.report.assessments]
        for index, finding in enumerate(outcome.report.findings, 1):
            confirmed = finding in outcome.evidence.confirmed
            lines += ["", f"## Проблема {index}: {finding.criterion_id} ({finding.severity})", "",
                f"Докази: {'підтверджені цитати' if confirmed else 'не підтверджено'}.", "", finding.explanation, "", finding.suggestion]
            for citation in finding.citations:
                lines += ["", f"{citation.document_id}, версія {citation.document_version}:", "", "> " + citation.quote.replace("\n", "\n> ")]
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary = folder / "outcome.json.tmp"
    temporary.write_text(outcome.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(folder / "outcome.json")
    return folder


def compare_reports(baseline: EvaluationOutcome, candidate: EvaluationOutcome) -> dict:
    def context(outcome):
        data = json.loads(json.dumps(outcome.metadata.get("snapshots", {})))
        case = data.get("case", {})
        for doc in case.get("documents", []):
            if doc["id"] in case.get("target_ids", []):
                doc["text"], doc["version"] = "<target>", "<version>"
        return {"case": case, "profile": data.get("profile"), "evaluator": outcome.metadata.get("evaluator_fingerprint"),
            "reverse_pair": outcome.metadata.get("reverse_pair", False)}

    if (baseline.status not in {"passed", "failed"} or candidate.status not in {"passed", "failed"}
            or not baseline.report or not candidate.report or context(baseline) != context(candidate)):
        return {"status": "non_comparable", "reasons": ["Входи/оцінювач відрізняються або звіт неповний"]}
    before = {a.criterion_id: a.score for a in baseline.report.assessments if a.score is not None}
    after = {a.criterion_id: a.score for a in candidate.report.assessments if a.score is not None}
    changes = {key: after[key] - before[key] for key in sorted(before.keys() & after.keys())}

    def findings(outcome):
        return {json.dumps({"criterion": f.criterion_id, "severity": f.severity,
            "citations": sorted((c.document_id, c.quote) for c in f.citations)}, ensure_ascii=False, sort_keys=True): f.model_dump()
            for f in outcome.evidence.confirmed}
    old, new = findings(baseline), findings(candidate)
    added = [new[key] for key in new.keys() - old.keys()]
    resolved = [old[key] for key in old.keys() - new.keys()]
    return {"status": "compared", "score_changes": changes, "added_findings": added, "resolved_findings": resolved,
        "regression": any(value < 0 for value in changes.values()) or any(f["severity"] in {"major", "critical"} for f in added)}
