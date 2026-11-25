from ob import *
s = scenes()
t = call('get_stage_task', scene_id=s[0], stage='edit')
prose = 'Олена вийшла з потяга на вокзалі в Житомирі. Над пероном висів старий годинник, стрілки якого стояли на десятій. Місто здавалося меншим, ніж вона пам’ятала. Вона поправила сірий плащ і рушила до будинку.'
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'], result=prose); p(r, 2000)
summary()
t = call('get_stage_task', scene_id=s[0], stage='memory')
print({k: (v if k not in ('material','instructions') else None) for k,v in t.items()})
print('INSTR', t['instructions'])
print('MAT', t['material'][-1500:])
