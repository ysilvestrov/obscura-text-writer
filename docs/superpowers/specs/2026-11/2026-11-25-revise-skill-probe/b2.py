"""Probe B (cont.): carry_failed details and chat redo of scene 2 memory."""
from ob import *
st = json.load(open('state_b.json')); s = st['s']
rid = http('GET', f'/api/stories/{sid()}/runs')[1]['runs'][0]['id']
print('get_run', json.dumps(call('get_run', run_id=rid), ensure_ascii=False)[:1500])
code, ev = http('GET', f'/api/runs/{rid}/events'); print('events', code, str(ev)[:1500])
print('s3 context:', str(call('get_scene_context', scene_id=s[2]))[:300])
print('s2 context:', str(call('get_scene_context', scene_id=s[1]))[:300])
for stage in ('memory', 'brief', 'edit'):
    t = call('get_stage_task', scene_id=s[1], stage=stage); print('s2', stage, 'task:', t.get('ERROR') or 'ok')
t, fr, cl = memory_task(s[1]); print('s2 sees claims now', json.dumps(cl, ensure_ascii=False))
mut = [m for m in cl['mutable'] if 'рюкзак' in m['text']]
r = save_memory(s[1], t, facts=['Олена поставила валізу в шафу.'], states_update=[(mut[0]['claim_id'], 'Рюкзак стоїть у шафі.')] if mut else []); print('s2 mem redo', r)
wait_runs(); summary()
for r in http('GET', f'/api/stories/{sid()}/runs')[1]['runs']: print('RUN', r['request']['mode'], r['state'], r['request']['scene_id'][:8])
for i in (1, 2): print(f's{i+1} links', json.dumps(links(s[i])['links'], ensure_ascii=False))
