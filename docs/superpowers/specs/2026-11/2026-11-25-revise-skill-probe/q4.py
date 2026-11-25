from ob import *
s = scenes()
st = call('get_settings', story_id=sid())
call('update_settings', story_id=sid(), section='editor', expected_fingerprint=st['roles']['editor']['fingerprint'], fields={'edit_review':'review'})
t = call('get_stage_task', scene_id=s[0], stage='edit')
import re
print('frag', re.findall(r'\[(f\d+)\]\n(.{0,60})', t['material'])[:2])
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'],
         result={'edits':[{'fragment_id':'f000001','original':'і стрілки стояли','replacement':'а стрілки стояли','category':'wording'}]}); p(r, 1500)
summary()
code, d = http('GET', f'/api/stories/{sid()}'); sc=[x for x in d['scenes'] if x['id']==s[0]][0]
print('heads', sc['heads'], 'needs_review', sc.get('needs_review')); print('ms', json.dumps(d['material_status'][s[0]], ensure_ascii=False)[:400])
print('PROSE head text:', call('get_scene_text', scene_id=s[0], material='prose')['text'][:90])
# Q4: save_draft while pending
r = do_draft(s[0], 'Олена вийшла з потяга на вокзалі у Львові. Над пероном висів старий годинник.'); p(r, 1500)
summary()
t = call('get_stage_task', scene_id=s[0], stage='edit'); print('edit task while pending:', {k:t.get(k) for k in ('result_format','task_fingerprint','ERROR')})
json.dump({'sid': sid(), 'pending_version': r.get('version_id') if isinstance(r, dict) else None}, open('state.json','w'))
