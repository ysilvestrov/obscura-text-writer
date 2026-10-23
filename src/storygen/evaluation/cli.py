import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .gateway import GatewayFailure, build_gateway, load_config
from .inputs import load_case, parse_json, read_json
from .models import EvaluationOutcome, ScoringProfile
from .prompting import build_request, load_rubric, resource_text
from .reports import compare_reports
from .runner import evaluate
from .scoring import load_profile
from ..billing.models import BudgetError
from ..storage.locking import AppInstanceLock


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parser() -> argparse.ArgumentParser:
    root = Parser(description="Автоматичне оцінювання української прози")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("evaluate", help="Оцінити текст")
    run.add_argument("--case", type=Path, required=True)
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--profile", type=Path)
    run.add_argument("--output", type=Path, default=Path("artifacts/evaluation"))
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--reverse-pair", action="store_true")
    run.add_argument('--budget-data-dir',type=Path,default=Path('data'))
    run.add_argument('--budget-scope')
    run.add_argument('--run-limit-usd')
    compare = commands.add_parser("compare", help="Порівняти два звіти")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    calibration = commands.add_parser("calibrate", help="Перевірити оцінювача на відомих дефектах")
    calibration.add_argument("--suite", type=Path, required=True)
    calibration.add_argument("--config", type=Path, required=True)
    calibration.add_argument("--profile", type=Path)
    calibration.add_argument("--output", type=Path, default=Path("artifacts/calibration"))
    calibration.add_argument("--repeats", type=int, default=3)
    calibration.add_argument("--dry-run", action="store_true")
    calibration.add_argument("--case-id", action="append")
    calibration.add_argument('--budget-data-dir',type=Path,default=Path('data'))
    calibration.add_argument('--budget-scope')
    calibration.add_argument('--run-limit-usd')
    return root


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    budget_lock = None
    try:
        args = parser().parse_args(argv)
        if args.command == "compare":
            before = EvaluationOutcome.model_validate(read_json(args.baseline))
            after = EvaluationOutcome.model_validate(read_json(args.candidate))
            result = compare_reports(before, after)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2 if result["status"] == "non_comparable" else int(result["regression"])
        config = load_config(args.config)
        import uuid
        budget_run_id=uuid.uuid4().hex
        def bind_budget(gateway):
            nonlocal budget_lock
            if args.dry_run or not hasattr(gateway,'bind_accounting'):return
            if config.provider in {'venice','openrouter'} and not args.budget_scope:
                raise BudgetError('Для cloud CLI потрібен --budget-scope')
            if not args.budget_scope: args.budget_scope = 'cli:evaluator'
            if budget_lock is None:
                budget_lock = AppInstanceLock(args.budget_data_dir)
                try: budget_lock.__enter__()
                except RuntimeError:
                    raise BudgetError('Каталог бюджету відкрито застосунком або іншим CLI; зупиніть його чи виберіть інший каталог') from None
            if args.budget_scope:
                from ..storage.repository import Repository
                from ..providers.accounting import CallAccounting
                gateway.bind_accounting(CallAccounting(Repository(args.budget_data_dir),args.budget_scope,budget_run_id,
                    uuid.uuid4().hex,run_limit_usd=args.run_limit_usd))
        rubric = load_rubric()
        profile = load_profile(args.profile) if args.profile else ScoringProfile.model_validate(parse_json(resource_text("scoring_candidate_v1.json")))
        if args.command == "calibrate":
            from .calibration import calibrate, load_suite
            from .runner import digest, evaluator_fingerprint
            if args.repeats < 1:
                raise ValueError("Кількість повторів має бути додатною")
            cases = load_suite(args.suite)
            if args.case_id:
                if not set(args.case_id) <= {case.id for case in cases}:
                    raise ValueError("Невідомий приклад")
                cases = [case for case in cases if case.id in args.case_id]
            if args.dry_run:
                print(json.dumps({"провайдер":config.provider,"приклади":[case.id for case in cases],"виклики":len(cases)*args.repeats},ensure_ascii=False,indent=2))
                return 0
            gateway = build_gateway(config)
            outcomes = []
            try:
                for case in cases:
                    for index in range(args.repeats):
                        print(f"Оцінювання {case.id}: {index + 1}/{args.repeats}", flush=True)
                        bind_budget(gateway)
                        outcomes.append(evaluate(case, rubric, profile, config, gateway, args.output / "runs", reverse_pair=bool(index % 2)))
                        if outcomes[-1].status == 'refused':
                            break
                    if outcomes[-1].status == 'refused':
                        break
            finally:
                close = getattr(gateway,"close",None)
                if close:
                    close()
            suite_data = read_json(args.suite)
            expectations = suite_data.get('expectations') or read_json(args.suite.parent / "expectations.json")
            metrics = calibrate(cases, expectations, outcomes, required_repeats=args.repeats)
            metrics["evaluator_fingerprint"] = evaluator_fingerprint(config, rubric)
            metrics['suite_version'] = suite_data.get('version')
            metrics['suite_hash'] = digest(suite_data)
            metrics['categories'] = suite_data.get('categories', {})
            metrics["run_ids"] = [o.metadata["run_id"] for o in outcomes]
            metrics["calibration_fingerprint"] = digest({"expectations":expectations,"outcomes":[o.model_dump() for o in outcomes]})
            if config.model is None:
                metrics["eligible"] = False
                metrics["model_note"] = "Для каліброваного профілю потрібен явний ідентифікатор моделі"
            args.output.mkdir(parents=True,exist_ok=True)
            target = args.output / "calibration.json"
            if target.exists():
                target = args.output / ("calibration-" + metrics["calibration_fingerprint"][:12] + ".json")
            target.write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
            print(f"Звіт калібрування: {target}")
            return 0 if metrics["eligible"] else 1
        case = load_case(args.case)
        request = build_request(case, rubric, config, args.reverse_pair)
        if args.dry_run:
            print(json.dumps({"провайдер":config.provider, "модель":config.model or "типова модель Codex CLI",
                "символів":sum(len(m["content"]) for m in request.messages), "документи":[d.id for d in case.documents]}, ensure_ascii=False, indent=2))
            return 0
        gateway = build_gateway(config)
        try:
            bind_budget(gateway)
            result = evaluate(case, rubric, profile, config, gateway, args.output, args.reverse_pair)
        finally:
            close = getattr(gateway, "close", None)
            if close:
                close()
        print(f"Оцінювання: {result.status}. Звіт: {result.metadata['report_path']}")
        return {"passed":0, "failed":1, "incomplete":2, "error":3, 'refused':4}[result.status]
    except (ValueError, OSError, ValidationError, GatewayFailure) as exc:
        message = str(exc) if isinstance(exc, (GatewayFailure, BudgetError)) else "Некоректні аргументи, конфігурація або файли"
        print(f"Помилка: {message}")
        return 3
    finally:
        if budget_lock is not None: budget_lock.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
