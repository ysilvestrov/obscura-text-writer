"""Editor bench CLI (#260 part 2).

  python scripts/editor_bench/run.py --plan     catalog check and worst-case cost; no model is called
  python scripts/editor_bench/run.py --paid     run the matrix (asks nothing: the owner approved it in chat)
  python scripts/editor_bench/run.py --report   aggregates from results.jsonl, without any text

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
        listed = {m.id: m for m in discover_models(ProviderSettings(provider=provider, model=models[0]))}
        for model in models:
            options[(provider, model)] = listed.get(model)
    return options


def candidate(provider, model, option):
    schema = option.supports_schema is not False if option else True
    context = min(option.context_tokens or 32768, 65536) if option else 32768
    output = min(option.max_output_tokens or 8192, 8192, context // 4) if option else 8192
    return stand.Candidate(provider, model, 'json_schema' if schema else 'prompt_json', context, output)


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


def plan():
    stand.load_keys(ENV_FILE)
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


def paid():
    rows, total = plan()
    texts = load_texts()
    if set(texts) != set(TEXTS):
        raise SystemExit(f'Бракує текстів: {sorted(set(TEXTS) - set(texts))}')
    if total > float(CAP_USD):
        raise SystemExit('Найгірший випадок перевищує ліміт; скоротіть матрицю')
    broken = broken_texts(texts)
    bench = stand.open_bench(stand.ROOT / 'data', {k: v[0] for k, v in broken.items()}, CAP_USD)
    out = stand.ROOT / 'results.jsonl'
    for text_id, c, worst in rows:
        left = float(CAP_USD) - stand.exposure_usd(bench)
        if worst > left:
            print(f'Пропущено {text_id} {c.code}: найгірший випадок ${worst:.3f} > залишку ${left:.3f}', flush=True)
            continue
        result = stand.run_loop(bench, text_id, c)
        gold = broken[text_id][1]
        result['score'] = score(gold, broken[text_id][0], result['edited']) if result.get('edited') else None
        with out.open('a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(f'{text_id} {c.code}: {result["state"]}, проходів {len(result.get("passes", []))}, '
              f'витрачено ${stand.exposure_usd(bench):.4f}', flush=True)
        if result['state'] == 'stand_error':
            raise SystemExit(f'Збій стенду ({result["error"]}); прогін зупинено без повторів')


def report():
    rows = [json.loads(line) for line in (stand.ROOT / 'results.jsonl').read_text(encoding='utf-8').splitlines() if line]
    models = {}
    for r in rows:
        models.setdefault(r['model'], []).append(r)
    print('| Модель | Тексти | Виправлено: орф. / пункт. / рус. | Інакше | Поза еталоном | Проходів | Прохід, с (медіана / p90) | Відмови / збої | Вартість, $ |')
    print('|---|---|---|---|---|---|---|---|---|')
    for model, items in models.items():
        scored = [r['score'] for r in items if r.get('score')]
        fixed = {c: sum(s[c]['fixed'] for s in scored) for c in CATEGORIES}
        total = {c: sum(s[c]['fixed'] + s[c]['missed'] + s[c]['other'] for s in scored) for c in CATEGORIES}
        other = sum(s[c]['other'] for s in scored for c in CATEGORIES)
        off = sum(s['off_gold_tokens'] for s in scored)
        passes = [p for r in items for p in r.get('passes', [])]
        seconds = sorted(p['seconds'] for p in passes if p.get('seconds') is not None and p['state'] == 'completed')
        median = statistics.median(seconds) if seconds else None
        p90 = seconds[min(len(seconds) - 1, int(0.9 * len(seconds)))] if seconds else None
        refusals = sum(p.get('refusal', False) for p in passes)
        failures = sum(1 for p in passes if p['state'] != 'completed') + sum(r['state'] == 'stand_error' for r in items)
        cost = sum(float(p['cost']) for p in passes if p.get('cost') is not None)
        share = ' / '.join(f'{fixed[c]}/{total[c]}' for c in CATEGORIES)
        print(f'| `{model}` | {",".join(r["text"] for r in items)} | {share} | {other} | {off} | {len(passes)} | '
              f'{median if median is not None else "—"} / {p90 if p90 is not None else "—"} | {refusals} / {failures} | {cost:.4f} |')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan', action='store_true')
    group.add_argument('--paid', action='store_true')
    group.add_argument('--report', action='store_true')
    args = parser.parse_args(argv)
    stand.isolated(stand.ROOT)
    plan() if args.plan else paid() if args.paid else report()


if __name__ == '__main__':
    main()
