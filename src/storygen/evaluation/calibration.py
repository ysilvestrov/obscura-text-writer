from collections import defaultdict
from pathlib import Path

from .inputs import contained_file, load_case, read_json
from .models import EvaluationCase, EvaluationOutcome, EvaluatorConfig, Rubric, ScoringProfile


def load_suite(path: Path) -> list[EvaluationCase]:
    data = read_json(path)
    cases = [load_case(contained_file(path.parent, name)) for name in data["cases"]]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Повтор ідентифікатора прикладу")
    return cases


def available(outcome: EvaluationOutcome) -> bool:
    return outcome.report is not None and outcome.status != "error" and all(
        reason == "profile_uncalibrated" or reason.startswith(("blocking_finding:", "below_threshold:"))
        for reason in outcome.reasons)


def matches(finding, expected, documents) -> bool:
    if finding.criterion_id != expected["criterion_id"]:
        return False
    for anchor in expected["anchors"]:
        text = documents.get(anchor["document_id"], "")
        start = text.find(anchor["quote"])
        if start < 0:
            raise ValueError("Очікуваний фрагмент відсутній у тесті")
        if not any(c.document_id == anchor["document_id"] and c.quote in text
            and max(start, text.find(c.quote)) < min(start + len(anchor["quote"]), text.find(c.quote) + len(c.quote))
            for c in finding.citations):
            return False
    return True


def calibrate(cases: list[EvaluationCase], expectations: dict, outcomes: list[EvaluationOutcome], required_repeats: int = 1) -> dict:
    if required_repeats < 1 or not cases:
        raise ValueError("Потрібні приклади та додатна кількість повторів")
    grouped = defaultdict(list)
    identities = set()
    run_ids = set()
    case_map = {case.id:case for case in cases}
    from .runner import digest, evaluator_fingerprint, fingerprint_inputs
    for outcome in outcomes:
        case_id = outcome.metadata.get("case_id") or outcome.metadata.get("snapshots", {}).get("case", {}).get("id")
        if case_id not in case_map:
            raise ValueError("Звіт не належить цьому набору")
        saved = outcome.metadata.get("snapshots", {})
        if saved.get("case") != case_map[case_id].model_dump():
            raise ValueError("Звіт стосується іншої версії прикладу")
        try:
            config = EvaluatorConfig.model_validate(saved["config"])
            rubric = Rubric.model_validate(saved["rubric"])
            profile = ScoringProfile.model_validate(saved["profile"])
        except (KeyError, ValueError) as exc:
            raise ValueError("Відсутня конфігурація походження звіту") from exc
        if (outcome.metadata.get("evaluator_fingerprint") != evaluator_fingerprint(config,rubric)
                or outcome.fingerprint != fingerprint_inputs(case_map[case_id],rubric,profile,config,outcome.metadata.get("reverse_pair",False))):
            raise ValueError("Звіт застарів або його конфігурацію змінено")
        run_id = outcome.metadata.get("run_id")
        if not run_id or run_id in run_ids:
            raise ValueError("Повторне використання того самого запуску не є незалежним повтором")
        run_ids.add(run_id)
        identities.add(digest({"config":saved["config"],"rubric":saved["rubric"],"profile":saved["profile"]}))
        if len(identities) != 1:
            raise ValueError("Не можна змішувати різних оцінювачів або профілі")
        grouped[case_id].append(outcome)
    tp = fp = misses = available_runs = unavailable_runs = critical_misses = critical_unknown = allowed_count = 0
    clean_runs = clean_false_positive_runs = 0
    stability = {}
    for case in cases:
        expected = expectations[case.id]["findings"]
        allowed = expectations[case.id].get("allowed_findings", [])
        docs = {doc.id: doc.text for doc in case.documents}
        for item in expected + allowed:
            if not item.get("anchors") or any(a["document_id"] not in docs or a["quote"] not in docs[a["document_id"]] for a in item["anchors"]):
                raise ValueError("Некоректні контрольні очікування")
        rows = grouped[case.id]
        absent = max(0, required_repeats - len(rows))
        unavailable_runs += absent
        critical_unknown += absent * sum(bool(item.get("critical")) for item in expected)
        scores = defaultdict(list)
        verdicts = set()
        by_order = defaultdict(list)
        for outcome in rows:
            if not available(outcome):
                unavailable_runs += 1
                critical_unknown += sum(bool(item.get("critical")) for item in expected)
                continue
            available_runs += 1
            remaining = list(expected)
            extra = []
            for finding in outcome.evidence.confirmed:
                match = next((item for item in remaining if matches(finding, item, docs)), None)
                if match is not None:
                    tp += 1
                    remaining.remove(match)
                elif any(matches(finding,item,docs) for item in allowed):
                    allowed_count += 1
                else:
                    fp += 1
                    extra.append(finding)
            misses += len(remaining)
            critical_misses += sum(bool(item.get("critical")) for item in remaining)
            if not expected:
                clean_runs += 1
                clean_false_positive_runs += int(any(f.severity in {"major", "critical"} for f in extra))
            for assessment in outcome.report.assessments:
                if assessment.score is not None:
                    scores[assessment.criterion_id].append(assessment.score)
            verdict = outcome.metadata.get("preliminary_verdict", outcome.status)
            verdicts.add(verdict)
            by_order[str(outcome.metadata.get("reverse_pair", False))].append(verdict)
        stability[case.id] = {"runs":len(rows), "required_repeats":required_repeats,
            "repeats_complete":len(rows) >= required_repeats, "score_ranges":{key:max(vals)-min(vals) if len(vals)>=2 else None for key,vals in scores.items()},
            "verdict_changed":len(verdicts) > 1 if sum(available(row) for row in rows) > 1 else None,
            "verdicts_by_order":dict(by_order)}
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    recall = ratio(tp, tp + misses)
    precision = ratio(tp, tp + fp)
    availability = ratio(available_runs, available_runs + unavailable_runs)
    fpr = ratio(clean_false_positive_runs, clean_runs)
    suite_complete = set(case_map) == set(expectations)
    eligible = (suite_complete and required_repeats >= 3 and recall is not None and recall >= 0.8 and fpr is not None and fpr <= 0.2
        and availability is not None and availability >= 0.9 and critical_misses == 0 and critical_unknown == 0
        and all(row["repeats_complete"] and row["verdict_changed"] is not True for row in stability.values()))
    return {"true_positives":tp,"false_positives":fp,"allowed_additional_findings":allowed_count,"misses":misses,"critical_misses":critical_misses,
        "critical_unchecked":critical_unknown,"available_runs":available_runs,"unavailable_runs":unavailable_runs,
        "recall":recall,"precision":precision,"false_positive_rate":fpr,"availability":availability,
        "stability":stability,"eligible":eligible,"suite_complete":suite_complete,
        "missing_case_ids":sorted(set(expectations) - set(case_map)),
        "metric_note":"null означає відсутній знаменник; мала вибірка не доводить загальної якості"}
