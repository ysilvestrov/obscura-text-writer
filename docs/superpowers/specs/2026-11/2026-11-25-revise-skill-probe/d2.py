"""Probe D (cont.): which material is stale after the brief is fixed, and does re-saving the same draft unblock edit."""
from ob import *
src = open(__file__.replace('d2.py', 'd.py'), encoding='utf-8').read().split("print('== D1/D2")[0]
exec(src)
for label in ('chat brief identical', 'author brief approval'):
    print('==', label)
    s = setup('Проба D2 ' + label)
    if label.startswith('chat'):
        b = call('get_scene_text', scene_id=s[1], material='brief'); t = call('get_stage_task', scene_id=s[1], stage='brief')
        call('save_stage_result', scene_id=s[1], stage='brief', task_fingerprint=t['task_fingerprint'], result=json.loads(b['text']))
    else:
        fp = links(s[1])['links']['brief']['fingerprint']; http('POST', f'/api/scenes/{s[1]}/links/brief/decision', json={'action': 'approve', 'fingerprint': fp})
    print('  stale flags:', {m: v.get('stale') for m, v in stale(s[1]).items()})
    d = call('get_scene_text', scene_id=s[1], material='draft')['text']
    print('  re-save same draft:', do_draft(s[1], d))
    tail(s, label + ' + same draft')
