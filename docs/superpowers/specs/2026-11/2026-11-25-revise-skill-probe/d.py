"""Probe D: resolving scene 2's unchecked brief after scene 1 changed — identical chat brief, accept-brief,
author brief-link approval; and a memory-only redo with changed claim text."""
from ob import *

def setup(title):
    new_story(title, n=3)
    s = scenes()
    for i, text in enumerate(['Олена приїхала до Житомира.', 'Олена відімкнула двері.', 'Олена вийшла в сад.']):
        do_brief(s[i], f'мета {i+1}'); do_draft(s[i], text); assert 'ERROR' not in do_edit_same(s[i]); do_memory(s[i], [text])
    do_draft(s[0], 'Олена приїхала до Вінниці.'); do_edit_same(s[0]); do_memory(s[0], ['Олена приїхала до Вінниці.']); wait_runs()
    return s

def tail(s, label):
    t = call('get_stage_task', scene_id=s[1], stage='edit'); print(f'  {label}: get_stage_task(edit):', t.get('ERROR') or 'ok')
    if 'ERROR' in t: return
    print('  edit identical to draft:', do_edit_same(s[1]))
    print('  memory:', do_memory(s[1], ['Олена відімкнула двері.'])); wait_runs(); summary()

print('== D1/D2: chat brief identical to the current one')
s = setup('Проба D1'); summary()
b = call('get_scene_text', scene_id=s[1], material='brief'); print('  current brief', b['version_id'], b['text'])
t = call('get_stage_task', scene_id=s[1], stage='brief')
r = call('save_stage_result', scene_id=s[1], stage='brief', task_fingerprint=t['task_fingerprint'], result=json.loads(b['text'])); print('  save brief:', r)
print('  new version differs:', isinstance(r, dict) and r.get('version_id') not in (None, b['version_id']))
summary(); print('  s2 links', json.dumps(links(s[1])['links'], ensure_ascii=False))
tail(s, 'D2')

print('== D3: author accept-brief on the current brief head')
s = setup('Проба D3'); b = call('get_scene_text', scene_id=s[1], material='brief')
rev = call('get_story', story_id=sid())['scenes'][1]['revision']
code, r = http('POST', f'/api/scenes/{s[1]}/accept-brief', json={'version_id': b['version_id'], 'expected_revision': rev}); print('  accept-brief', code, str(r)[:200])
summary(); tail(s, 'D3 after accept-brief')
print('== D3b: author "Я перевірив сам" for the brief link only (links/brief/decision)')
fp = links(s[1])['links']['brief']['fingerprint']
print('  decision', http('POST', f'/api/scenes/{s[1]}/links/brief/decision', json={'action': 'approve', 'fingerprint': fp}))
summary(); tail(s, 'D3b after brief approval')

print('== D4: memory-only redo with changed claim text (prose unchanged, links valid)')
s = setup('Проба D4')
fp = links(s[1])['links']; [http('POST', f'/api/scenes/{s[1]}/links/{l}/decision', json={'action': 'approve', 'fingerprint': fp[l]['fingerprint']}) for l in ('brief', 'prose')]
summary(); n0 = len(runs())
print('  s2 memory redo:', do_memory(s[1], ['Олена відімкнула двері в Одесі.'])); wait_runs(); summary()
print('  new runs:', runs()[: len(runs()) - n0])
print('  s2 memory:', call('get_scene_text', scene_id=s[1], material='memory')['text'])
