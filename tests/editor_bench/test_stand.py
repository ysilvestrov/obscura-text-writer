"""Editor bench stand on a fake gateway: the product's edit_loop path, isolation and key handling, no network."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from editor_bench import stand  # noqa: E402
from editor_bench.inject import inject  # noqa: E402
from editor_bench.score import score  # noqa: E402
from storygen.providers.streaming import GenerationEvent  # noqa: E402
from tests.editor_bench.test_inject_score import text  # noqa: E402


@pytest.fixture
def bench_root(tmp_path, monkeypatch):
    monkeypatch.setattr(stand, 'ROOT', tmp_path)
    return tmp_path


def test_a_data_folder_outside_the_bench_root_is_refused(bench_root, tmp_path_factory):
    with pytest.raises(ValueError, match='всередині'):
        stand.isolated(tmp_path_factory.mktemp('elsewhere'))
    assert stand.isolated(bench_root / 'data') == (bench_root / 'data').resolve()


def test_only_the_two_provider_keys_are_loaded(tmp_path, monkeypatch):
    for name in ('VENICE_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / '.env'
    env.write_text('VENICE_API_KEY=v-test\nOPENAI_API_KEY=o-test\n', encoding='utf-8')
    assert stand.load_keys(env) == ['VENICE_API_KEY']
    assert os.environ['VENICE_API_KEY'] == 'v-test' and 'OPENAI_API_KEY' not in os.environ


def test_a_loop_runs_through_the_product_and_scores(bench_root, monkeypatch):
    monkeypatch.setenv('PYTHON_KEYRING_BACKEND', 'keyring.backends.fail.Keyring')
    original = text()
    broken, gold = inject(original, seed=4)
    half = broken
    for m in sorted(gold[::2], key=lambda m: m.start, reverse=True):
        half = half[:m.start] + m.right + half[m.start + len(m.wrong):]
    calls = []

    class Fake:
        def stream(self, ctx, cancel):
            calls.append(ctx.stage)
            yield GenerationEvent(type='delta', text=half)
            yield GenerationEvent(type='terminal', finish_reason='stop')

    bench = stand.open_bench(bench_root / 'data', {'N': broken}, '3')
    result = stand.run_loop(bench, 'N', stand.Candidate('local', 'fake', 'prompt_json'), gateway_factory=lambda settings: Fake())
    assert result['state'] in {'needs_review', 'completed'}, result
    assert result['stop_reason'] == 'no_changes' and len(result['passes']) == 2 == len(calls)
    assert all(p['seconds'] is not None for p in result['passes'])
    counts = score(gold, broken, result['edited'])
    assert sum(counts[c]['fixed'] for c in ('spelling', 'punctuation', 'russism')) == len(gold[::2])
    assert 'test' not in json.dumps({k: v for k, v in result.items() if k != 'edited'})


def test_the_next_model_edits_the_same_broken_text(bench_root, monkeypatch):
    monkeypatch.setenv('PYTHON_KEYRING_BACKEND', 'keyring.backends.fail.Keyring')
    broken, gold = inject(text(), seed=4)
    seen = []

    class Fake:
        def stream(self, ctx, cancel):
            seen.append(broken[:200] in ctx.user_text)
            yield GenerationEvent(type='delta', text=text())
            yield GenerationEvent(type='terminal', finish_reason='stop')

    bench = stand.open_bench(bench_root / 'data', {'N': broken}, '3')
    first = stand.run_loop(bench, 'N', stand.Candidate('local', 'one', 'prompt_json'), gateway_factory=lambda s: Fake())
    second = stand.run_loop(bench, 'N', stand.Candidate('local', 'two', 'prompt_json'), gateway_factory=lambda s: Fake())
    assert first['state'] == second['state'] == 'needs_review', (first, second)
    assert seen[0] and seen[2], seen  # each model's first pass reads the broken text
    assert score(gold, broken, second['edited'])['off_gold_tokens'] == 0


def test_a_second_part_reuses_the_bench_and_its_budget(bench_root):
    first = stand.open_bench(bench_root / 'data', {'N': text()}, '3')
    again = stand.open_bench(bench_root / 'data', {'N': text(), 'S': text()}, '3')
    assert again.stories['N'] == first.stories['N'] and set(again.stories) == {'N', 'S'}


@pytest.mark.parametrize('text_id', ['V', 'S'])
def test_rated_texts_run_with_consent_and_an_adult_cast(bench_root, monkeypatch, text_id):
    monkeypatch.setenv('PYTHON_KEYRING_BACKEND', 'keyring.backends.fail.Keyring')
    broken, _ = inject(text(), seed=4)

    class Fake:
        def stream(self, ctx, cancel):
            yield GenerationEvent(type='delta', text=text())
            yield GenerationEvent(type='terminal', finish_reason='stop')

    cast = {'S': [{'id': 'A', 'name': 'Перша', 'age': 30}, {'id': 'B', 'name': 'Другий', 'age': 'дорослий'}]}
    bench = stand.open_bench(bench_root / 'data', {text_id: broken}, '3', cast)
    story = bench.repo.get_story(bench.stories[text_id][0])
    assert tuple(story.content_rating.model_dump().values()) == stand.RATINGS[text_id]
    # A cloud model without uncensored=true: the stand records the consent the owner gave in chat.
    from storygen.providers import policy
    monkeypatch.setattr(policy, 'needs_consent', lambda settings, uncensored, rating: any(rating))
    result = stand.run_loop(bench, text_id, stand.Candidate('local', 'fake', 'prompt_json'), gateway_factory=lambda s: Fake())
    assert result['state'] == 'needs_review', result
