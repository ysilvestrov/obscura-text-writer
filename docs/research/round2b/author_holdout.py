"""Offline stage-3 materializer. No model clients; private inputs stay private.

Usage: python -m round2b.author_holdout --input PRIVATE.json --author-model ID
       python -m round2b.author_holdout --self-check
"""
import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import random
import re
import secrets
import unicodedata

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
PROMPT_SHA = '55fe4d840642b93c69d01d1b2a4d5d421282b99e51bf6ac054d27028593a9088'
FAMILIES = {'A': 2, 'B': 4, 'C': 2, 'D': 2, 'E': 2}
BANNED = [('а', 'не'), ('вперше', 'в', 'житті'), ('ніколи',),
          ('не', 'чіпаючи'), ('саме', 'той'), ('тієї', 'єдиної')]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def words(text):
    text = unicodedata.normalize('NFC', text).casefold().replace("'", '’').replace('ʼ', '’')
    return re.findall(r"[^\W_]+(?:’[^\W_]+)*", text, re.UNICODE)


def ngrams(tokens, n):
    return set(tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1))


def mechanical_case(row):
    target = words(row['target'])
    if any(tuple(phrase) in ngrams(target, len(phrase)) for phrase in BANNED):
        raise ValueError(f'{row["id"]}: banned construct')
    if ngrams(words(' '.join(row['sources'])), 4) & ngrams(target, 4):
        raise ValueError(f'{row["id"]}: shared 4gram')
    outside = set(words(' '.join(row['sources'][1:]) + ' ' + row['target']))
    if (not row['frame_names'] or set(row['frame_names']) != set(row['characters'])
            or any(not set(words(name)) <= outside for name in row['frame_names'])):
        raise ValueError(f'{row["id"]}: frame characters absent outside frame')
    # Frame is generated, not supplied free-form: no undeclared names can enter it.
    if row['sources'][0] != frame(row['characters'], row['context']):
        raise ValueError(f'{row["id"]}: unexpected frame')


def frame(names, context):
    people = ', '.join(f'{name} (30 років)' for name in names)
    singular = len(names) == 1
    if context == 'neutral':
        setting = 'Вона працює' if singular else 'Вони працюють'
        setting += ' над фотографіями міських будівель.'
    else:
        setting = 'Вона бере' if singular else 'Вони беруть'
        setting += ' участь у добровільній приватній фотосесії ню. Усі учасники повнолітні й погодили межі зйомки.'
    return f'Персонажі епізоду: {people}. {setting} Інші події прямо задані окремими передумовами.'


def check_pair(a, b):
    if a['family'] == 'D':
        if a['target'] != b['target']:
            raise ValueError('D target must be identical')
        if b['sources'][:-1] != a['sources']:
            raise ValueError('D priority must be a separate appended source')
        left, right = '\n'.join(a['sources']), '\n'.join(b['sources'])
    else:
        if a['sources'] != b['sources']:
            raise ValueError('Only D may change premises')
        left, right = a['target'], b['target']
    if not left or not right or not .85 <= len(left) / len(right) <= 1.15:
        raise ValueError('Pair length outside 0.85–1.15')
    # Words including attached punctuation retain punctuation-only edits, too.
    edits = [op for op in SequenceMatcher(None, left.split(), right.split(), autojunk=False).get_opcodes()
             if op[0] != 'equal']
    if len(edits) != 1:
        raise ValueError('Pair must change exactly one fragment')


def validate_structure(cases):
    if len(cases) != 48 or len({r['id'] for r in cases}) != 48:
        raise ValueError('Expected 48 unique cases')
    groups = defaultdict(list)
    counts = Counter()
    for row in cases:
        f, v, ctx = row['family'], row['variant'], row['context']
        if f not in FAMILIES or v not in ('a', 'b') or ctx not in ('neutral', 'adult'):
            raise ValueError('Unexpected design cell')
        groups[row['template']].append(row)
        verdict = ('question' if v == 'a' else 'clean') if f == 'D' else ('issue' if f == 'E' or v == 'b' else 'clean')
        gold = row['gold']
        n = 2 if f == 'E' and v == 'a' else int(verdict == 'issue')
        if gold['verdict'] != verdict or len(gold['contradictions']) != n:
            raise ValueError('Gold structure disagrees with design')
        if len({x['id'] for x in gold['contradictions']}) != n:
            raise ValueError('Duplicate fact ID')
        for fact in gold['contradictions']:
            if not fact['target_quote'] or fact['target_quote'] not in row['target']:
                raise ValueError('Missing exact gold quote')
            if (not fact['source_indices'] or any(type(i) is not int or not 1 <= i < len(row['sources'])
                                                 for i in fact['source_indices'])):
                raise ValueError('Invalid source index')
            if not fact['type'] or fact['severity'] not in ('minor', 'major', 'critical'):
                raise ValueError('Incomplete fact')
        if verdict != 'issue' and not gold[f'{verdict}_reason'].strip():
            raise ValueError('Missing rationale')
        if not row['target'].strip() or not all(s.strip() for s in row['sources']):
            raise ValueError('Empty input')
        if row['ages'] != [30] * len(row['characters']):
            raise ValueError('Explicit adult ages required')
        counts[(ctx, verdict)] += 1
        counts['facts'] += n
        mechanical_case(row)
    if Counter(rows[0]['family'] for rows in groups.values()) != FAMILIES:
        raise ValueError('Wrong template family distribution')
    for rows in groups.values():
        if len(rows) != 4 or len({r['family'] for r in rows}) != 1 or {
            (r['context'], r['variant']) for r in rows} != {(c,v) for c in ('neutral','adult') for v in ('a','b')}:
            raise ValueError('Incomplete template quartet')
        for ctx in ('neutral', 'adult'):
            a, b = [next(r for r in rows if r['context'] == ctx and r['variant'] == v) for v in ('a','b')]
            check_pair(a, b)
        for v in ('a', 'b'):
            a, b = [next(r for r in rows if r['context'] == ctx and r['variant'] == v) for ctx in ('neutral','adult')]
            if (a['sources'][1:], a['target'], a['gold']) != (b['sources'][1:], b['target'], b['gold']):
                raise ValueError('Context must change only frame')
    if counts != Counter({(c,v): n for c in ('neutral','adult') for v,n in [('clean',10),('issue',12),('question',2)]}) + Counter(facts=28):
        raise ValueError('Wrong counts')


def make_cases(templates):
    cases = []
    for t in templates:
        for ctx in ('neutral', 'adult'):
            for v in ('a', 'b'):
                sources = [frame(t['characters'], ctx)] + t['sources'] + ([t['priority']] if t['family'] == 'D' and v == 'b' else [])
                cases.append(dict(id=f'{t["id"]}-{ctx}-{v}', template=t['id'], family=t['family'],
                    variant=v, context=ctx, characters=t['characters'], frame_names=t['characters'],
                    ages=[30]*len(t['characters']), sources=sources, target=t[v], gold=t['gold'][v]))
    return cases


def blind_order(cases, seed):
    rng = random.Random(seed)
    for _ in range(10000):
        order = list(cases)
        rng.shuffle(order)
        if all(a['template'] != b['template'] for a,b in zip(order, order[1:])):
            return order
    raise ValueError('Unable to separate templates')


def render_blind(order, prompt):
    out = ['# Holdout 2b — сліпа панель автора', '',
           'Позначте один варіант на кожен приклад. Не потрібно складати JSON.',
           '`clean` — сумісно; `issue` — конкретна суперечність; `question` — істотна невизначеність за промптом.',
           'Для issue скопіюйте цільову цитату, бажано вкажіть S-джерело й коротко поясніть конфлікт. Якщо суперечностей кілька — зазначте кожну.',
           'Для question коротко поясніть, що потребує рішення. Номери S/T локальні для кожного прикладу.',
           'Після завершення збережіть файл і повідомте в чаті. Ключ до розмітки не відкривайте.', '',
           '## Зафіксований промпт A′ v1', '', '```text', prompt.strip(), '```', '']
    for position, row in enumerate(order, 1):
        out += [f'## Приклад {position:02d}', '', '**Передумови**', '']
        out += [f'- S{i}. {s}' for i,s in enumerate(row['sources'], 1)]
        out += ['', '**Цільовий текст**', '', f'T1. {row["target"]}', '',
                '- [ ] clean', '- [ ] issue', '- [ ] question', '- Цитата для issue:',
                '- Джерело та пояснення / питання:', '']
    return '\n'.join(out)


def fingerprint(row):
    return sha(json.dumps(dict(sources=row['sources'], target=row['target']), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def render_revision(order, prompt, review):
    """Retain stable positions; reset only content revisions, never compare gold."""
    items = review['items']
    statuses = {'recheck', 'frame_only', 'unchanged'}
    if (len(items) != len(order) or {x['position'] for x in items} != set(range(1, len(order)+1))
            or any(x['status'] not in statuses for x in items)):
        raise ValueError('Invalid review revision positions/statuses')
    header = render_blind([], prompt).split('## Зафіксований промпт', 1)
    revision = review.get('revision', 2)
    archive = review.get('original_annotation_archive', 'oracle-blind-v1-annotated.md')
    repair = review.get('single_template_repair', False)
    recheck_templates = {order[x['position']-1]['template'] for x in items if x['status'] == 'recheck'}
    if repair and len(recheck_templates) != 1:
        raise ValueError('Single-template repair requires exactly one template')
    out = [header[0].replace('# Holdout 2b — сліпа панель автора', f'# Holdout 2b — виправлена панель, редакція {revision}'),
           '**Перегляньте лише розділ «Повторно оцінити».** Нижче збережено попередні позначки й коментарі для прикладів із виправленням лише рамки та без змін.',
           f'Номери прикладів збережені з першої панелі. Попередню розмітку повністю збережено в {archive}.',
           ('Це точковий перегляд однієї групи вже знайомих прикладів, не новий незалежний сліпий раунд.' if repair else ''), '',
           '## Зафіксований промпт' + header[1]]
    headings = [('recheck', 'Повторно оцінити'), ('frame_only', 'Лише виправлення рамки'), ('unchanged', 'Без змін')]
    for status, title in headings:
        selected = [x for x in items if x['status'] == status]
        if status == 'recheck' and not repair and any(order[a['position']-1]['template'] == order[b['position']-1]['template']
                                       for a,b in zip(selected, selected[1:])):
            raise ValueError('Adjacent template in recheck section; separate paired examples first')
        out += [f'## {title} — {len(selected)}', '']
        for item in selected:
            position = item['position']
            row = order[position-1]
            block = render_blind([row], prompt).split('## Приклад 01', 1)[1]
            if status == 'recheck':
                note = ('Уточнено зміст дії; потрібна повторна оцінка.' if item.get('change_kind', 'content') == 'content'
                        else 'Виправлено рамку; у попередній панелі оцінку не поставлено.')
                block = '\n\n' + note + block
            if status != 'recheck':
                block = block.split('- [ ] clean', 1)[0] + item['annotation'].rstrip() + '\n'
            out += [f'### Приклад {position:02d}' + block, '']
    return '\n'.join(out).rstrip() + '\n'


def self_check(folder):
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest['source_sha256'] != sha(Path(__file__).read_bytes()):
        raise ValueError('Stage-3 generator changed after materializing')
    for name, digest in manifest['files'].items():
        if sha((folder/name).read_bytes()) != digest:
            raise ValueError(f'Changed stage-3 file: {name}')
    prompt = (folder/'prompts/check-aprime-v1-uk.txt').read_bytes()
    if sha(prompt) != PROMPT_SHA:
        raise ValueError('Prompt changed after owner approval')
    cases = json.loads((folder/'holdout-draft.json').read_text(encoding='utf-8'))
    validate_structure(cases)
    key = json.loads((folder/'oracle-key.json').read_text(encoding='utf-8'))
    order = blind_order(cases, key['seed'])
    expected = [dict(position=i, case_id=r['id'], gold=r['gold']) for i,r in enumerate(order, 1)]
    if key['positions'] != expected:
        raise ValueError('Key does not match deterministic ordering')
    revision_file = manifest.get('review_revision_file')
    if revision_file:
        review = json.loads((folder/revision_file).read_text(encoding='utf-8'))
        expected_panel = render_revision(order, prompt.decode('utf-8'), review)
    else:
        expected_panel = render_blind(order, prompt.decode('utf-8'))
    if (folder/'oracle-blind.md').read_text(encoding='utf-8') != expected_panel:
        raise ValueError('Blind panel changed (owner labels require later separate audit)')
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--author-model')
    args = parser.parse_args()
    if args.self_check:
        print(f'Self-check PASS: {self_check(FOLDER)} cases; no inference')
        return
    if not args.input or not args.author_model:
        parser.error('--input and owner-confirmed --author-model required')
    outputs = ['holdout-draft.json', 'oracle-key.json', 'oracle-blind.md', 'manifest.json']
    if any((FOLDER/n).exists() for n in outputs):
        raise SystemExit('Stage-3 outputs exist: refusing to overwrite owner review')
    approval = json.loads((FOLDER/'aprime-iterations.json').read_text(encoding='utf-8'))
    if not approval.get('prompt_frozen') or approval['owner_decision']['decision'] != 'approve_aprime_v1_for_holdout_preparation':
        raise ValueError('Owner approval required before materializing')
    prompt = (FOLDER/'prompts/check-aprime-v1-uk.txt').read_bytes()
    if sha(prompt) != PROMPT_SHA:
        raise ValueError('Wrong frozen prompt')
    cases = make_cases(json.loads(args.input.read_text(encoding='utf-8')))
    validate_structure(cases)
    old = json.loads((ROOT/'docs/research/round2/holdout.json').read_text(encoding='utf-8'))
    dev = json.loads((FOLDER/'dev-d-cases.json').read_text(encoding='utf-8'))
    prohibited = {fingerprint(r) for r in old+dev}
    if len({fingerprint(r) for r in cases}) != 48 or any(fingerprint(r) in prohibited for r in cases):
        raise ValueError('Duplicate/old/dev input reused')
    seed = secrets.token_hex(32)
    order = blind_order(cases, seed)
    key = dict(seed=seed, positions=[dict(position=i, case_id=r['id'], gold=r['gold']) for i,r in enumerate(order,1)])
    files = {'holdout-draft.json': encoded(cases), 'oracle-key.json': encoded(key),
             'oracle-blind.md': render_blind(order, prompt.decode('utf-8')).encode('utf-8')}
    manifest = dict(stage='holdout-2b-drafts-awaiting-owner-oracle', date='2026-10-30',
        author_model=args.author_model, author_identity_source='owner confirmation in this chat, 2026-10-30',
        prompt_sha256=PROMPT_SHA, prompt_approval_commit='768550e',
        input_sha256=sha(args.input.read_bytes()), seed_sha256=sha(seed.encode()),
        files={n:sha(b) for n,b in files.items()}, cases=48, self_check='passed before render',
        model_calls=0, owner_oracle_pending=True, dataset_frozen=False,
        l6_invalid_must_be_reported_separately=True,
        source_sha256=sha(Path(__file__).read_bytes()))
    for name, data in files.items():
        with (FOLDER/name).open('xb') as stream:
            stream.write(data)
    with (FOLDER/'manifest.json').open('xb') as stream:
        stream.write(encoded(manifest))
    print(f'Stage 3 written; self-check PASS: {self_check(FOLDER)} cases. STOP; no inference.')


if __name__ == '__main__':
    main()
