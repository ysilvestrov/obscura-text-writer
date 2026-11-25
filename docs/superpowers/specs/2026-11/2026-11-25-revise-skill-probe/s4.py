from ob import *
s = scenes()
t = call('get_stage_task', scene_id=s[0], stage='edit')
print(list(t.keys())); m=t['material']; print(type(m), repr(m[-300:]) if isinstance(m,str) else m)
