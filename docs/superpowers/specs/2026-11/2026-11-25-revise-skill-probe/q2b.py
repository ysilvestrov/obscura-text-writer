from ob import *
s = scenes()
t = call('get_stage_task', scene_id=s[0], stage='edit')
print('result_format', t['result_format'], 'revision', t['revision'])
print('MAT tail', repr(t['material'][-330:]))
draft = call('get_scene_text', scene_id=s[0], material='draft')['text']
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'], result=draft); p(r, 1500)
summary()
st = stale(s[0]); print({m: (v.get('version_id'), v.get('stale'), v.get('kind')) for m,v in st.items()})
st = stale(s[1]); print('s2', {m: (v.get('version_id'), v.get('stale'), v.get('kind')) for m,v in st.items()})
code, d = http('GET', f'/api/stories/{sid()}')
print('s1 ms', json.dumps(d['material_status'][s[0]], ensure_ascii=False))
print('s2 ms', json.dumps(d['material_status'][s[1]], ensure_ascii=False))
print('RUNS', http('GET', f'/api/stories/{sid()}/runs'))
