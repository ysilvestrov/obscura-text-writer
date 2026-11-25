"""Probe B: memory_carry after scene 1 claim ids change while scene 2 updates/retires a scene-1 claim."""
from ob import *
new_story('Проба B')
s = scenes()
def pre(sc, text):
    do_brief(sc, 'x'); do_draft(sc, text); r = do_edit_same(sc); assert 'ERROR' not in r, r
pre(s[0], 'Олена приїхала до Житомира з валізою.')
t, fr, cl = memory_task(s[0]); print('s1 claims before', cl)
print('s1 mem', save_memory(s[0], t, facts=['Олена приїхала до Житомира.'], states_add=['Олена тримає валізу.']))
pre(s[1], 'Олена поставила валізу в шафу.')
t, fr, cl = memory_task(s[1]); print('s2 sees claims', json.dumps(cl, ensure_ascii=False))
cid = [m for m in cl['mutable'] if 'валіз' in m['text']][0]['claim_id']
print('s2 mem (update)', save_memory(s[1], t, facts=['Олена поставила валізу в шафу.'], states_update=[(cid, 'Валіза стоїть у шафі.')]))
pre(s[2], 'Олена вийшла в сад.')
t, fr, cl = memory_task(s[2]); print('s3 sees claims', json.dumps(cl, ensure_ascii=False))
print('s3 mem', save_memory(s[2], t, facts=['Олена вийшла в сад.']))
summary(); print('runs', runs())
print('== change scene 1 prose inside quoted fragment, redo memory with new claim texts')
do_draft(s[0], 'Олена приїхала до Вінниці з рюкзаком.'); print('edit', do_edit_same(s[0]))
t, fr, cl = memory_task(s[0])
print('s1 mem redo', save_memory(s[0], t, facts=['Олена приїхала до Вінниці.'], states_add=['Олена тримає рюкзак.']))
wait_runs(); summary()
for r in http('GET', f'/api/stories/{sid()}/runs')[1]['runs']:
    print('RUN', r['request']['mode'], r['state'], r['request']['scene_id'][:8], r['id'])
for i in (1, 2):
    print(f's{i+1} links', json.dumps(links(s[i]), ensure_ascii=False))
json.dump({'sid': sid(), 's': s}, open('state_b.json', 'w'))
