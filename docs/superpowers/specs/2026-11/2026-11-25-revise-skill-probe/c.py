"""Probe C: (1) author manual draft via the editor's HTTP path; (2) which own-event field changes memory_digest."""
from ob import *
from storygen.memory.journal import load_memory
from storygen.storage.links import own_events
new_story('Проба C', n=2)
s = scenes()
do_brief(s[0], 'x')
# (1) the editor saves a draft: POST /api/scenes/{id}/draft without external_origin (static/versions.js:72)
rev = call('get_scene_context', scene_id=s[0])['revision']
code, r = http('POST', f'/api/scenes/{s[0]}/draft', json={'text': 'Олена приїхала до Житомира.\n\nНа пероні пахло дощем.', 'expected_revision': rev, 'content_format': 'markdown'})
print('author draft', code, {k: r['version'].get(k) for k in ('id', 'kind', 'external_origin')})
d = call('get_scene_text', scene_id=s[0], material='draft'); print('get_scene_text(draft):', {k: d.get(k) for k in ('version_id', 'kind', 'external_origin', 'stale')})
print('edit after author draft', do_edit_same(s[0])); summary()
# chat-made chain for (2)
do_draft(s[0], 'Олена приїхала до Житомира.\n\nНа пероні пахло дощем.'); do_edit_same(s[0])
def own(mem_id):
    code, v = http('GET', f'/api/versions/{mem_id}')
    return [e.model_dump(mode='json') for e in own_events(load_memory(v['text']))]
r1 = do_memory(s[0], ['Олена приїхала до Житомира.']); e1 = own(r1['version_id'])
do_draft(s[0], 'Олена приїхала до Житомира.\n\nНа пероні пахло снігом.'); do_edit_same(s[0])
r2 = do_memory(s[0], ['Олена приїхала до Житомира.']); e2 = own(r2['version_id'])
print('EVENT 1', json.dumps(e1, ensure_ascii=False, indent=1))
print('EVENT 2', json.dumps(e2, ensure_ascii=False, indent=1))
skip = {'event_id', 'source_version_id', 'evidence_version_id'}
def diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in skip: continue
            diff(a.get(k), b.get(k), f'{path}.{k}')
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)): diff(x, y, f'{path}[{i}]')
    elif a != b:
        print('DIFF', path, '|', json.dumps(a, ensure_ascii=False), '->', json.dumps(b, ensure_ascii=False))
diff(e1, e2)
