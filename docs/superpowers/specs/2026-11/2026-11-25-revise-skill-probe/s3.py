from ob import *
s = scenes()
p(do_brief(s[0], 'Олена приїздить до Житомира.'), 1500)
p(do_draft(s[0], 'Олена вийшла з потяга на вокзалі в Житомирі. Над пероном висів старий годинник, і стрілки стояли на десятій. Місто здавалося меншим, ніж вона пам’ятала. Вона поправила сірий плащ і пішла до будинку.'), 1500)
t = call('get_stage_task', scene_id=s[0], stage='edit')
print({k: (v if k not in ('material','instructions') else None) for k,v in t.items()})
print('INSTR', t['instructions'][:4000])
print('MAT', str(t['material'])[-2500:])
summary()
