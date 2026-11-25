from ob import *
s = scenes()
t = call('get_stage_task', scene_id=s[0], stage='edit')
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'], result={'edits':[]}); p(r, 1500)
summary()
print('PROSE now:', call('get_scene_text', scene_id=s[0], material='prose')['text'][:80])
st = stale(s[0]); print({m: (v.get('version_id'), v.get('stale'), v.get('kind')) for m,v in st.items()})
# is there another edit task (multi-pass)?
t2 = call('get_stage_task', scene_id=s[0], stage='edit'); print('edit task again', t2.get('result_format'), t2.get('task_fingerprint', t2)[:20] if isinstance(t2.get('task_fingerprint'),str) else t2)
print('ATTEMPTS', [ (a.get('stage'), a.get('state'), a.get('error')) for a in (http('GET', f'/api/stories/{sid()}/attempts')[1] or {}).get('attempts', [])][-4:] if http('GET', f'/api/stories/{sid()}/attempts')[0]==200 else 'no attempts endpoint')
