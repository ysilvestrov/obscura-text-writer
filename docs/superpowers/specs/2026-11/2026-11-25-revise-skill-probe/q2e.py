from ob import *
s = scenes()
p(do_draft(s[0], 'Олена вийшла з потяга на вокзалі в Одесі. Над пероном висів старий годинник, і стрілки стояли на десятій. Місто здавалося меншим, ніж вона пам’ятала. Вона поправила сірий плащ і пішла до будинку.'))
summary()
t = call('get_stage_task', scene_id=s[0], stage='edit')
print('result_format', t['result_format'])
print('INSTR', t['instructions'][:2500])
