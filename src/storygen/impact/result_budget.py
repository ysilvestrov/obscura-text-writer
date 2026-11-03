"""Budget only data delivered to a model; keep derived coverage in the audit."""
import json

LEGACY_CAP_ERROR='Відповідь частини перевищила погоджений резерв'
REVISION='wire2-derived-coverage-budget-v2'


def compact_size(value):return len(json.dumps(value,ensure_ascii=False,separators=(',',':')))


def budget_size(canonical,wire_version):
    if wire_version==2:canonical={k:v for k,v in canonical.items() if k!='covered_ids'}
    return compact_size(canonical)


def recoverable_failure(attempt):
    return (attempt.stage=='impact_part' and attempt.state=='failed' and attempt.finish_reason=='stop'
        and (attempt.error or '').startswith(LEGACY_CAP_ERROR))
