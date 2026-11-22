"""Editor bench CLI (#260 part 2).

  python scripts/editor_bench/run.py --plan     catalog check and worst-case cost; no model is called
  python scripts/editor_bench/run.py --paid     run the matrix (asks nothing: the owner approved it in chat)
  python scripts/editor_bench/run.py --report   aggregates from results.jsonl, without any text
  --suite reasoning   the #260 re-run of three OpenRouter editors with a reasoning effort (OPENROUTER-REASONING):
                      its own key file, data folder, results file and cap

Texts live in C:\\tmp\\editor-bench\\texts\\{N,V,T,S}.txt and never enter the repository. Without --paid no model is called.
"""
import argparse
import json
import statistics
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor_bench import stand  # noqa: E402
from editor_bench.inject import CATEGORIES, inject  # noqa: E402
from editor_bench.score import score  # noqa: E402

ENV_FILE = Path(r'C:\Projects\text-generator\.env')
CAP_USD = '3'
SEED = 260
V, O = 'venice', 'openrouter'
# Order: cheap first, expensive last, so a stop by budget loses the least.
VENICE = ['gemma-4-uncensored', 'glm-5-3-flash-uncensored', 'venice-uncensored-1-2', 'e2ee-gemma-4-26b-a4b-uncensored-p',
          'aion-labs-aion-3-5-mini', 'qwen-3-6-plus']
OPENROUTER = ['z-ai/glm-5.3-flash', 'qwen/qwen3.8-flash', 'google/gemma-4-31b-it', 'openai/gpt-6-luna',
              'anthropic/claude-haiku-5.5', 'qwen/qwen3.7-plus', 'openai/gpt-6.1-sol']
TEXTS = {'N': (V, O), 'V': (V, O), 'T': (V, O), 'S': (V,)}  # the sexual-axis text goes to Venice only
NEUTRAL_ONLY = {'openai/gpt-6.1-sol'}  # the Quality editor: one text keeps the worst case within the cap
EFFORT = {}  # model -> OpenRouter reasoning effort; empty for the #260 matrix
DATA_DIR = stand.ROOT / 'data'
RESULTS = stand.ROOT / 'results.jsonl'
CHARS_PER_TOKEN = 2.5
PROMPT_OVERHEAD_TOKENS = 2500


def texts_dir():
    return stand.ROOT / 'texts'


def load_texts():
    found = {}
    for text_id in TEXTS:
        path = texts_dir() / f'{text_id}.txt'
        if path.exists():
            found[text_id] = path.read_text(encoding='utf-8').strip() + '\n'
    return found


def broken_texts(texts):
    """Inject once per text with a fixed seed; the gold list stays next to the texts, locally."""
    result = {}
    for text_id, text in texts.items():
        broken, gold = inject(text, SEED)
        (texts_dir() / f'{text_id}.gold.json').write_text(
            json.dumps([m.__dict__ for m in gold], ensure_ascii=False, indent=1), encoding='utf-8')
        result[text_id] = (broken, gold)
    return result


def catalog():
    from storygen.providers.discovery import discover_models
    from storygen.providers.models import ProviderSettings
    options = {}
    for provider, models in ((V, VENICE), (O, OPENROUTER)):
        if not models:
            continue
        listed = {m.id: m for m in discover_models(ProviderSettings(provider=provider, model=models[0]))}
        for model in models:
            options[(provider, model)] = listed.get(model)
    return options


def candidate(provider, model, option):
    schema = option.supports_schema is not False if option else True
    context = min(option.context_tokens or 32768, 65536) if option else 32768
    output = min(option.max_output_tokens or 8192, 8192, context // 4) if option else 8192
    return stand.Candidate(provider, model, 'json_schema' if schema else 'prompt_json', context, output, EFFORT.get(model))


def matrix(texts, options):
    """(text id, candidate, worst-case usd) in run order: by text, then cheap → expensive within the text."""
    rows = []
    for text_id in TEXTS:
        if text_id not in texts:
            continue
        for provider, models in ((V, VENICE), (O, OPENROUTER)):
            if provider not in TEXTS[text_id]:
                continue
            for model in models:
                if model in NEUTRAL_ONLY and text_id != 'N':
                    continue
                option = options.get((provider, model))
                if option is None or option.tariff is None:
                    continue
                c = candidate(provider, model, option)
                tokens_in = len(texts[text_id]) / CHARS_PER_TOKEN + PROMPT_OVERHEAD_TOKENS
                one = (Decimal(str(tokens_in)) * option.tariff.input_per_million
                       + Decimal(c.max_output_tokens) * option.tariff.output_per_million) / Decimal(1_000_000) + option.tariff.request_usd
                rows.append((text_id, c, float(one * stand.PASS_LIMIT)))
    return rows


def isolate_credentials():
    """Turn the OS credential store off for this process: a key missing from ENV_FILE must not come from the owner's store."""
    import os
    os.environ['PYTHON_KEYRING_BACKEND'] = 'keyring.backends.fail.Keyring'


def require_keys():
    """Load the keys of the providers in the matrix from ENV_FILE; stop when one is missing."""
    needed = {name for name, models in (('VENICE_API_KEY', VENICE), ('OPENROUTER_API_KEY', OPENROUTER)) if models}
    missing = sorted(needed - set(stand.load_keys(ENV_FILE)))
    if missing:
        raise SystemExit(f'Бракує ключів у {ENV_FILE}: {", ".join(missing)}')


def plan():
    require_keys()
    texts = load_texts()
    options = catalog()
    print('Тексти:', {k: f'{len(v.split())} слів' for k, v in texts.items()} or 'немає')
    for (provider, model), option in options.items():
        if option is None:
            print(f'  НЕМАЄ В КАТАЛОЗІ: {provider}:{model}')
        else:
            notes = [f'вхід {option.tariff.input_per_million}/вихід {option.tariff.output_per_million}' if option.tariff else 'ціна невідома',
                     'uncensored' if option.uncensored else '', 'без JSON Schema' if option.supports_schema is False else '',
                     f'прибирають {option.retirement.date}' if option.retirement else '']
            print(f'  {provider}:{model}: ' + ', '.join(n for n in notes if n))
    rows = matrix(texts, options)
    total = sum(r[2] for r in rows)
    print(f'Циклів: {len(rows)}; найгірший випадок: ${total:.2f} (ліміт ${CAP_USD})')
    by_model = {}
    for _, c, usd in rows:
        by_model[c.code] = by_model.get(c.code, 0) + usd
    for code, usd in sorted(by_model.items(), key=lambda item: -item[1]):
        print(f'  {code}: ${usd:.3f}')
    return rows, total


def paid(only):
    rows, total = plan()
    texts = load_texts()
    texts = {k: v for k, v in texts.items() if k in TEXTS}
    if set(texts) != set(TEXTS):
        raise SystemExit(f'Бракує текстів: {sorted(set(TEXTS) - set(texts))}')
    if total > float(CAP_USD):
        raise SystemExit('Найгірший випадок перевищує ліміт; скоротіть матрицю')
    texts = {k: v for k, v in texts.items() if k in only}
    rows = [r for r in rows if r[0] in only]
    broken = broken_texts(texts)
    casts = {k: json.loads((texts_dir() / f'{k}.cast.json').read_text(encoding='utf-8'))
             for k in texts if (texts_dir() / f'{k}.cast.json').exists()}
    bench = stand.open_bench(DATA_DIR, {k: v[0] for k, v in broken.items()}, CAP_USD, casts)
    out = RESULTS
    for text_id, c, worst in rows:
        left = float(CAP_USD) - stand.exposure_usd(bench)
        if worst > left:
            print(f'Пропущено {text_id} {c.code}: найгірший випадок ${worst:.3f} > залишку ${left:.3f}', flush=True)
            continue
        result = stand.run_loop(bench, text_id, c)
        gold = broken[text_id][1]
        result['score'] = _scored(result, broken[text_id])
        with out.open('a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(f'{text_id} {c.code}: {result["state"]}, проходів {len(result.get("passes", []))}, '
              f'витрачено ${stand.exposure_usd(bench):.4f}', flush=True)
        if result['state'] == 'stand_error':
            raise SystemExit(f'Збій стенду ({result["error"]}); прогін зупинено без повторів')


def _scored(row, broken_gold):
    """The score of one loop, or None when no pass completed: such a loop edited nothing and counts as a failure."""
    broken, gold = broken_gold
    if not row.get('edited') or not any(p['state'] == 'completed' for p in row.get('passes', [])):
        return None
    return score(gold, broken, row['edited'])


def rescore(rows, broken):
    """Recompute every score from the saved edited text (offline, after a scorer change)."""
    return [r | {'score': _scored(r, broken[r['text']])} for r in rows]


def aggregate(rows, texts):
    """Per model over the given text ids: fixed per category, gold size, other, off-gold, pass seconds, failures and the
    ledger's counted cost (failed passes included). Counts only."""
    result = {}
    for r in rows:
        if r['text'] not in texts:
            continue
        m = result.setdefault(r['model'], {'texts': [], 'fixed': {c: 0 for c in CATEGORIES},
                                           'lenient': {c: 0 for c in CATEGORIES}, 'gold': 0, 'other': 0, 'off_gold': 0,
                                           'passes': 0, 'seconds': [], 'refusals': 0, 'failures': 0, 'failed_loops': 0,
                                           'loops': 0, 'cost_usd': 0.0, 'words_kept': []})
        m['texts'].append(r['text'])
        m['loops'] += 1
        m['failed_loops'] += r['state'] not in ('needs_review', 'completed')
        # A loop with no completed pass edited nothing: it is a failure, not "0 fixed".
        s = r.get('score') if any(p['state'] == 'completed' for p in r.get('passes', [])) else None
        if s:
            for c in CATEGORIES:
                m['fixed'][c] += s[c]['fixed']
                m['lenient'][c] += s[c].get('fixed_lenient', 0)
                m['gold'] += s[c]['fixed'] + s[c]['missed'] + s[c]['other']
                m['other'] += s[c]['other']
            m['off_gold'] += s['off_gold_tokens']
            m['words_kept'].append(s.get('words_kept', 1.0))
        for p in r.get('passes', []):
            m['passes'] += 1
            m['refusals'] += bool(p.get('refusal'))
            m['failures'] += p['state'] != 'completed'
            if p['state'] == 'completed' and p.get('seconds') is not None:
                m['seconds'].append(p['seconds'])
            m['cost_usd'] += (p.get('accounting') or {}).get('counted_nanos') or 0
    for m in result.values():
        m['cost_usd'] = round(m['cost_usd'] / 1e9, 6)
        kept = m.pop('words_kept')
        m['words_kept_min'] = min(kept) if kept else None
        seconds = sorted(m.pop('seconds'))
        m['median_seconds'] = statistics.median(seconds) if seconds else None
        m['p90_seconds'] = seconds[min(len(seconds) - 1, int(0.9 * len(seconds)))] if seconds else None
    return result


def _results():
    return [json.loads(line) for line in RESULTS.read_text(encoding='utf-8').splitlines() if line]


def rescore_file():
    broken = {k: inject(v, SEED) for k, v in load_texts().items()}
    stand.open_bench(DATA_DIR, {k: v[0] for k, v in broken.items()}, CAP_USD)  # refuses a text changed since the run
    rows = rescore(_results(), broken)
    RESULTS.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'Переоцінено циклів: {len(rows)}')


def report():
    rows = _results()
    for title, texts in (('Загальні тексти N, V, T', 'NVT'), ('Сексуальна вісь S (лише Venice)', 'S')):
        print(f'\n### {title}\n')
        print('| Модель | Оцінено / циклів | М\'яко: орф. / пункт. / рус. | М\'яко разом | Строго разом | Поза еталоном, токенів '
              '| Слів лишилось, мін. | Проходів | Прохід, с (медіана / p90) | Відмови / збої проходів | Вартість, $ |')
        print('|---|---|---|---|---|---|---|---|---|---|---|')
        for model, m in aggregate(rows, texts).items():
            per = m['gold'] // 3
            share = ' / '.join(f"{m['lenient'][c]}/{per}" for c in CATEGORIES) if m['gold'] else '—'
            lenient = f"{sum(m['lenient'].values())}/{m['gold']}" if m['gold'] else '—'
            strict = f"{sum(m['fixed'].values())}/{m['gold']}" if m['gold'] else '—'
            sec = f"{m['median_seconds']:.0f} / {m['p90_seconds']:.0f}" if m['median_seconds'] is not None else '—'
            kept = f"{m['words_kept_min']:.0%}" if m['words_kept_min'] is not None else '—'
            print(f"| `{model}` | {m['gold'] // 30}/{m['loops']} | {share} | {lenient} | {strict} | {m['off_gold']} | {kept} | {m['passes']} | {sec} | "
                  f"{m['refusals']} / {m['failures']} | {m['cost_usd']:.4f} |")
    print('\n### М\'яко разом за текстами\n')
    print('| Модель | ' + ' | '.join(TEXTS) + ' |')
    print('|---|' + '---|' * len(TEXTS))
    per_text = {t: aggregate(rows, t) for t in TEXTS}
    for model in aggregate(rows, ''.join(TEXTS)):
        cells = [f"{sum(per_text[t][model]['lenient'].values())}/{per_text[t][model]['gold']}" if model in per_text[t] and per_text[t][model]['gold']
                 else ('збій' if model in per_text[t] else '') for t in TEXTS]
        print(f'| `{model}` | ' + ' | '.join(cells) + ' |')


def use_reasoning_suite():
    """Three OpenRouter editors that spent the whole 8192-token output on reasoning in #260, now with an effort set:
    glm's reasoning is mandatory (lowest level `low`), both qwen models allow `none`. The same texts, seed and limits."""
    global VENICE, OPENROUTER, TEXTS, NEUTRAL_ONLY, EFFORT, CAP_USD, ENV_FILE, DATA_DIR, RESULTS
    EFFORT = {'z-ai/glm-5.3-flash': 'low', 'qwen/qwen3.8-flash': 'none', 'qwen/qwen3.7-plus': 'none'}
    VENICE, OPENROUTER = [], list(EFFORT)
    TEXTS = {'N': (O,), 'V': (O,), 'T': (O,)}
    NEUTRAL_ONLY = set()
    CAP_USD = '0.5'  # approved by the owner in chat on 2026-11-22: 9 loops, up to 45 passes
    ENV_FILE = stand.ROOT / '.env.reasoning'
    DATA_DIR = stand.ROOT / 'data-reasoning'
    RESULTS = stand.ROOT / 'results-reasoning.jsonl'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan', action='store_true')
    group.add_argument('--paid', action='store_true')
    group.add_argument('--report', action='store_true')
    group.add_argument('--rescore', action='store_true', help='recompute scores from results.jsonl; no model is called')
    parser.add_argument('--texts', default=''.join(TEXTS), help='which texts to run with --paid, e.g. NVT')
    parser.add_argument('--suite', choices=('260', 'reasoning'), default='260')
    args = parser.parse_args(argv)
    if args.suite == 'reasoning':
        use_reasoning_suite()
    isolate_credentials()
    stand.isolated(stand.ROOT)
    if args.rescore:
        return rescore_file()
    plan() if args.plan else paid(set(args.texts)) if args.paid else report()


if __name__ == '__main__':
    main()
