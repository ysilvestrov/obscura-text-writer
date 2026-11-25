from ob import *
s = scenes()
c = call('get_scene_context', scene_id=s[1]); print(json.dumps(c, ensure_ascii=False)[:600])
summary()
