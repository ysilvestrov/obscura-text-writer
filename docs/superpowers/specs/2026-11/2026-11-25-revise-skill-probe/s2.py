from ob import *
import json
sid = json.load(open('state.json'))['sid']
st = call('get_story', story_id=sid)
p(call('update_story', story_id=sid, expected_revision=st['revision'], content_rating={'sexual':0,'violence':0,'themes':0}))
s1 = st['scenes'][0]['id']
t = call('get_stage_task', scene_id=s1, stage='brief')
print({k: (v if k!='material' and k!='instructions' else str(v)[:200]) for k,v in t.items()})
print('INSTR', t['instructions'][-3000:])
print('MAT', str(t['material'])[:3000])
