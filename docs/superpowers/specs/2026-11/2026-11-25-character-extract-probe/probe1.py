"""R-51 probe: sequential extraction of characters, locations and scene cast in word-budget groups.

Usage: python -I probe.py <text.txt> <model> <group_words> <out.json>
Reads OPENROUTER_API_KEY from C:/Projects/text-generator/.env; never prints it.
"""
import json, re, sys, time
from pathlib import Path
import httpx
from dotenv import dotenv_values

KEY = dotenv_values(r'C:\Projects\text-generator\.env')['OPENROUTER_API_KEY']
URL = 'https://openrouter.ai/api/v1/chat/completions'
SCENE_WORDS = 1000

SYSTEM = """Ти аналізуєш прозу української книги, щоб скласти картки персонажів, локацій і склад сцен.
Правила:
- Лише те, що є в тексті; нічого не вигадуй.
- Кожна нова картка персонажа має 1–3 ДОСЛІВНІ цитати з наданого тексту (точний підрядок, 5–25 слів), що показують цього персонажа.
- Якщо персонаж уже є в каталозі (зокрема під іншим іменем, зменшувальним, прізвищем, прізвиськом, у відмінку) — НЕ створюй нову картку, а додай нове ім'я до наявної (card_updates).
- Персонаж — істота, що діє або говорить у сцені чи важлива для сюжету; групи («люди», «гуцули») не є персонажами.
- Локація — конкретне місце дії (село, хата, полонина, ліс тощо); вкладене місце пиши як «Батьківське / Підмісце».
- Для КОЖНОЇ сцени групи вкажи учасників (присутні в сцені) і локацію.
- Кандидати в головного героя — ті, навколо кого обертається текст, з оцінкою 0–1.
Відповідай ЛИШЕ JSON за схемою:
{"new_cards":[{"key":"new1","name":"...","other_names":["..."],"quotes":["..."]}],
 "card_updates":[{"id":"c1","other_names":["..."]}],
 "new_locations":[{"key":"newloc1","path":"..."}],
 "scenes":[{"scene":3,"participants":["c1","new1"],"location":"loc1 або newloc1 або null"}],
 "protagonist_candidates":[{"id":"c1 або new1","score":0.8}]}"""


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


def catalogue_text(cards, locs):
    c = '\n'.join(f'{cid}: {v["name"]}' + (f' (інші імена: {", ".join(v["other_names"])})' if v['other_names'] else '') for cid, v in cards.items()) or '(порожньо)'
    l = '\n'.join(f'{lid}: {p}' for lid, p in locs.items()) or '(порожньо)'
    return f'Каталог персонажів:\n{c}\n\nКаталог локацій:\n{l}'


def call(model, messages):
    for attempt in range(3):
        try:
            r = httpx.post(URL, headers={'Authorization': f'Bearer {KEY}'}, timeout=300, json={
                'model': model, 'messages': messages, 'temperature': 0.2, 'max_tokens': 16000,
                'response_format': {'type': 'json_object'}, 'usage': {'include': True}})
            r.raise_for_status(); d = r.json()
            content = d['choices'][0]['message']['content']
            content = re.sub(r'^```(?:json)?|```$', '', content.strip(), flags=re.M).strip()
            return json.loads(content), d.get('usage', {})
        except Exception as e:  # noqa: BLE001
            err = f'{type(e).__name__}: {str(e)[:200]}'
            time.sleep(3)
    return {'error': err}, {}


def main(path, model, budget, out):
    text = Path(path).read_text(encoding='utf-8')
    scenes = scenes_of(text)
    cards, locs, cast, protag = {}, {}, {}, {}
    quotes, cost, errors = [], 0.0, 0
    for g in groups_of(scenes, int(budget)):
        body = '\n\n'.join(f'=== Сцена {i} ===\n{scenes[i]}' for i in g)
        res, usage = call(model, [{'role': 'system', 'content': SYSTEM},
                                  {'role': 'user', 'content': catalogue_text(cards, locs) + f'\n\nСцени {g[0]}–{g[-1]}:\n\n' + body}])
        cost += float(usage.get('cost') or 0)
        if 'error' in res:
            errors += 1; print('ERR', g, res['error'], file=sys.stderr); continue
        keymap = {}
        for nc in res.get('new_cards', []):
            cid = f'c{len(cards)+1}'; keymap[nc.get('key')] = cid
            cards[cid] = {'name': nc.get('name', ''), 'other_names': list(nc.get('other_names') or []), 'first_group': g[0]}
            for q in nc.get('quotes') or []:
                quotes.append({'card': cid, 'quote': q, 'verbatim': q in body})
        for cu in res.get('card_updates', []):
            if cu.get('id') in cards:
                cards[cu['id']]['other_names'] += [n for n in cu.get('other_names') or [] if n not in cards[cu['id']]['other_names']]
        for nl in res.get('new_locations', []):
            lid = f'loc{len(locs)+1}'; keymap[nl.get('key')] = lid; locs[lid] = nl.get('path', '')
        for sc in res.get('scenes', []):
            cast[sc.get('scene')] = {'participants': [keymap.get(p, p) for p in sc.get('participants') or []],
                                     'location': keymap.get(sc.get('location'), sc.get('location'))}
        for pc in res.get('protagonist_candidates', []):
            pid = keymap.get(pc.get('id'), pc.get('id'))
            protag[pid] = protag.get(pid, 0) + float(pc.get('score') or 0)
    result = {'model': model, 'group_words': int(budget), 'scenes': len(scenes), 'groups': len(groups_of(scenes, int(budget))),
              'errors': errors, 'cost_usd': round(cost, 5), 'cards': cards, 'locations': locs, 'cast': cast,
              'protagonist': sorted(protag.items(), key=lambda x: -x[1])[:3],
              'quotes_total': len(quotes), 'quotes_verbatim': sum(q['verbatim'] for q in quotes),
              'bad_quotes': [q for q in quotes if not q['verbatim']][:10]}
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(model, budget, 'cards', len(cards), 'locs', len(locs), 'quotes', result['quotes_verbatim'], '/', len(quotes),
          'errors', errors, 'cost', result['cost_usd'], 'protag', result['protagonist'][:1])


if __name__ == '__main__':
    main(*sys.argv[1:5])
