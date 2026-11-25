"""R-51 probe 2: the spec-1 contract (characters and scene cast only), sequential word-budget groups.

Usage: python -I probe2.py <text.txt> <model> <group_words> <max_tokens> <out.json>
Reads OPENROUTER_API_KEY from C:/Projects/text-generator/.env; never prints it.
Scenes are mechanical ~1000-word chunks; the model sees short aliases s<N> (scenes) and c<N> (cards).
Quotes are checked after normalisation; an alias is grounded when its stem (name minus 2 trailing letters,
at least 3 letters) starts a word of the group prose.
"""
import json, re, sys, time, unicodedata
from pathlib import Path
import httpx
from dotenv import dotenv_values

KEY = dotenv_values(r'C:\Projects\text-generator\.env')['OPENROUTER_API_KEY']
URL = 'https://openrouter.ai/api/v1/chat/completions'
SCENE_WORDS = 1000

SYSTEM = """Ти читаєш прозу книги групами сцен, щоб скласти картки персонажів і склад кожної сцени.
Правила:
- Лише те, що є в тексті; нічого не вигадуй.
- Персонаж — істота, що діє або говорить у сцені чи важлива для сюжету; групи людей не є персонажами.
- Оповідач від першої особи («я») — теж персонаж: якщо його ім'я десь назване, використай ім'я, інакше назви картку «Оповідач».
- Нова картка має 1–2 ДОСЛІВНІ цитати з наданого тексту (точний підрядок, 5–20 слів), що показують цього персонажа.
- Якщо персонаж уже є в каталозі (зокрема під іншим іменем, зменшувальним, прізвищем, прізвиськом, у відмінку) — НЕ створюй нову картку, а додай нове ім'я до наявної (card_updates). Імена пиши в називному відмінку.
- Для КОЖНОЇ сцени групи вкажи учасників — персонажів, присутніх у сцені.
- Кандидати в головного героя — до 3, ті, навколо кого обертається текст групи, з оцінкою 0–1.
Відповідай ЛИШЕ JSON:
{"new_cards":[{"key":"n1","name":"...","other_names":["..."],"quotes":["..."]}],
 "card_updates":[{"id":"c1","other_names":["..."]}],
 "scenes":[{"scene":"s3","participants":["c1","n1"]}],
 "protagonist_candidates":[{"id":"c1 або n1","score":0.8}]}"""


def norm(s):
    s = unicodedata.normalize('NFC', s)
    s = re.sub(r'[\u2010-\u2015\u2212-]', '-', s)
    s = re.sub(r"[’ʼ'`]", "'", s)
    s = re.sub(r'[«»„“”"]', '"', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.strip(' ."\u2026').lower()


def scenes_of(text):
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    scenes, cur, words = [], [], 0
    for p in paras:
        cur.append(p); words += len(p.split())
        if words >= SCENE_WORDS:
            scenes.append('\n\n'.join(cur)); cur, words = [], 0
    if cur: scenes.append('\n\n'.join(cur))
    return scenes


def groups_of(scenes, budget):
    out, cur, words = [], [], 0
    for i, s in enumerate(scenes):
        w = len(s.split())
        if cur and words + w > budget:
            out.append(cur); cur, words = [], 0
        cur.append(i); words += w
    if cur: out.append(cur)
    return out


def grounded(name, prose_words):
    stem = norm(name)
    stem = stem[:-2] if len(stem) > 5 else stem
    return any(w.startswith(stem) for w in prose_words)


def call(model, messages, max_tokens):
    err = None
    for attempt in range(2):
        try:
            r = httpx.post(URL, headers={'Authorization': f'Bearer {KEY}'}, timeout=300, json={
                'model': model, 'messages': messages, 'temperature': 0.2, 'max_tokens': int(max_tokens),
                'response_format': {'type': 'json_object'}, 'usage': {'include': True}})
            r.raise_for_status(); d = r.json()
            ch = d['choices'][0]
            content = re.sub(r'^```(?:json)?|```$', '', (ch['message']['content'] or '').strip(), flags=re.M).strip()
            usage = d.get('usage', {})
            return json.loads(content), usage, attempt
        except Exception as e:  # noqa: BLE001
            err = f'{type(e).__name__}: {str(e)[:200]}'
            time.sleep(2)
    return {'error': err}, {}, 1


def main(path, model, budget, max_tokens, out):
    scenes = scenes_of(Path(path).read_text(encoding='utf-8'))
    cards, cast, protag = {}, {}, {}
    q_total = q_ok = a_total = a_ok = retries = errors = bad_scene = 0
    cost, max_out = 0.0, 0
    for g in groups_of(scenes, int(budget)):
        body = '\n\n'.join(f'=== Сцена s{i+1} ===\n{scenes[i]}' for i in g)
        nbody = norm(body)
        words = re.findall(r"[\w']+", nbody)
        cat = '\n'.join(f'{cid}: {v["name"]}' + (f' (інші імена: {", ".join(v["other_names"])})' if v['other_names'] else '')
                        for cid, v in cards.items()) or '(порожньо)'
        res, usage, att = call(model, [{'role': 'system', 'content': SYSTEM},
                                       {'role': 'user', 'content': f'Каталог персонажів:\n{cat}\n\nСцени s{g[0]+1}–s{g[-1]+1}:\n\n{body}'}], max_tokens)
        retries += att; cost += float(usage.get('cost') or 0); max_out = max(max_out, int(usage.get('completion_tokens') or 0))
        if 'error' in res:
            errors += 1; print('ERR', g, res['error'], file=sys.stderr); continue
        keymap = {}
        for nc in res.get('new_cards', []):
            qs = [q for q in nc.get('quotes') or [] if isinstance(q, str)]
            ok = [q for q in qs if norm(q) and norm(q) in nbody]
            q_total += len(qs); q_ok += len(ok)
            names = [n for n in nc.get('other_names') or [] if isinstance(n, str)]
            a_total += len(names); gnames = [n for n in names if grounded(n, words)]; a_ok += len(gnames)
            if not ok:
                continue  # a card with no verbatim quote is not proposed
            cid = f'c{len(cards)+1}'; keymap[nc.get('key')] = cid
            cards[cid] = {'name': nc.get('name', ''), 'other_names': gnames, 'first_scene': g[0] + 1}
        for cu in res.get('card_updates', []):
            if cu.get('id') in cards:
                names = [n for n in cu.get('other_names') or [] if isinstance(n, str) and n not in cards[cu['id']]['other_names']]
                a_total += len(names); gnames = [n for n in names if grounded(n, words)]; a_ok += len(gnames)
                cards[cu['id']]['other_names'] += gnames
        valid_scenes = {f's{i+1}' for i in g}
        for sc in res.get('scenes', []):
            if sc.get('scene') not in valid_scenes:
                bad_scene += 1; continue
            cast[sc['scene']] = [keymap.get(p, p) for p in sc.get('participants') or [] if keymap.get(p, p) in cards]
        for pc in res.get('protagonist_candidates', []):
            pid = keymap.get(pc.get('id'), pc.get('id'))
            if pid in cards:
                protag[pid] = protag.get(pid, 0) + float(pc.get('score') or 0)
    top = sorted(protag.items(), key=lambda x: -x[1])[:3]
    result = {'model': model, 'group_words': int(budget), 'max_tokens': int(max_tokens), 'scenes': len(scenes),
              'groups': len(groups_of(scenes, int(budget))), 'errors': errors, 'retries': retries, 'cost_usd': round(cost, 5),
              'max_completion_tokens': max_out, 'quotes': f'{q_ok}/{q_total}', 'aliases_grounded': f'{a_ok}/{a_total}',
              'bad_scene_ids': bad_scene, 'scenes_with_cast': f'{len(cast)}/{len(scenes)}',
              'protagonist': [(cards[p]['name'], round(s, 2)) for p, s in top], 'cards': cards, 'cast': cast}
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cards', 'cast')}, ensure_ascii=False))
    print('cards:', '; '.join(f'{v["name"]} ({", ".join(v["other_names"])})' for v in cards.values()))


if __name__ == '__main__':
    main(*sys.argv[1:6])
