"""Editor bench report aggregation: counts, seconds and the ledger's cost, without any text."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from editor_bench.run import aggregate  # noqa: E402


def _score(fixed, missed, other, off, kept=1.0):
    return {c: {'fixed': fixed, 'missed': missed, 'other': other, 'fixed_lenient': fixed + other} for c in ('spelling', 'punctuation', 'russism')} | {'off_gold_tokens': off, 'words_kept': kept}


def _pass(state='completed', seconds=10.0, nanos=1_000_000, failure=None):
    return {'state': state, 'seconds': seconds, 'cost': {'usd': nanos / 1e9, 'diem': 0}, 'refusal': False,
            'failure': failure, 'accounting': {'counted_nanos': nanos}}


def test_aggregate_skips_the_score_of_a_loop_without_a_completed_pass_and_sums_the_ledger_cost():
    rows = [
        {'text': 'N', 'model': 'venice:m', 'state': 'needs_review', 'passes': [_pass(seconds=10), _pass(seconds=30)], 'score': _score(5, 3, 2, 40, kept=0.8)},
        {'text': 'S', 'model': 'venice:m', 'state': 'needs_review', 'passes': [_pass(seconds=20)], 'score': _score(7, 1, 2, 10)},
        {'text': 'N', 'model': 'openrouter:r', 'state': 'failed',
         'passes': [_pass(state='failed', seconds=130, nanos=4_000_000, failure='error')], 'score': _score(0, 10, 0, 0)},
    ]
    general = aggregate(rows, texts='NVT')
    assert general['venice:m']['fixed'] == {'spelling': 5, 'punctuation': 5, 'russism': 5}
    assert general['venice:m']['lenient'] == {'spelling': 7, 'punctuation': 7, 'russism': 7}
    assert general['venice:m']['gold'] == 30 and general['venice:m']['off_gold'] == 40
    assert general['venice:m']['median_seconds'] == 20 and general['venice:m']['passes'] == 2
    assert general['venice:m']['cost_usd'] == 0.002 and general['venice:m']['words_kept_min'] == 0.8
    failed = general['openrouter:r']
    assert failed['failed_loops'] == 1 and failed['failures'] == 1 and failed['cost_usd'] == 0.004 and failed['gold'] == 0
    adult = aggregate(rows, texts='S')
    assert set(adult) == {'venice:m'} and adult['venice:m']['fixed']['spelling'] == 7


def test_rescore_recomputes_from_the_saved_text_and_drops_a_loop_without_a_completed_pass():
    from editor_bench.inject import inject
    from editor_bench.run import rescore
    from tests.editor_bench.test_inject_score import text
    original = text()
    broken, gold = inject(original, 260)
    rows = [{'text': 'N', 'model': 'a', 'passes': [_pass()], 'edited': original, 'score': None},
            {'text': 'N', 'model': 'b', 'passes': [_pass(state='failed')], 'edited': broken, 'score': _score(0, 10, 0, 0)}]
    done = rescore(rows, {'N': (broken, gold)})
    assert done[0]['score']['spelling']['fixed'] == 10 and done[0]['score']['spelling']['fixed_lenient'] == 10
    assert done[1]['score'] is None
