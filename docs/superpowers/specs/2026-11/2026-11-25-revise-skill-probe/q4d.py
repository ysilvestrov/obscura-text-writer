from ob import *
s = scenes()
st = call('get_settings', story_id=sid())
call('update_settings', story_id=sid(), section='editor', expected_fingerprint=st['roles']['editor']['fingerprint'], fields={'edit_mode':'prose','edit_review':'review'})
t = call('get_stage_task', scene_id=s[0], stage='edit'); print('fmt', t['result_format'])
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'], result='Олена вийшла з потяга на вокзалі у Львові. Над пероном висів старий годинник.'); p(r, 800)
summary()
code, d = http('GET', f'/api/stories/{sid()}'); sc=[x for x in d['scenes'] if x['id']==s[0]][0]; print('heads.prose', sc['heads']['prose'], 'needs_review', sc.get('needs_review'))
# same identical text: prose identical to draft under prose mode already tested in auto. Now patches+review apply path
call('update_settings', story_id=sid(), section='editor', expected_fingerprint=call('get_settings', story_id=sid())['roles']['editor']['fingerprint'], fields={'edit_mode':'patches'})
p(do_draft(s[0], 'Олена вийшла з потяга на вокзалі в Києві. Над пероном висів старий годинник, і стрілки стояли на десятій.'), 400)
t = call('get_stage_task', scene_id=s[0], stage='edit')
r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'],
   result={'edits':[{'fragment_id':'f000001','original':'і стрілки стояли','replacement':'а стрілки стояли','category':'wording'}]}); p(r, 600)
atts = http('GET', f'/api/scenes/{s[0]}/copyedits')[1]['attempts']; print('attempts', atts)
aid = [a for a in atts if a['state']=='needs_review'][-1]['id']
code, pv = http('GET', f'/api/scenes/{s[0]}/copyedits/{aid}')
rev = call('get_scene_context', scene_id=s[0])['revision']
code, r = http('POST', f'/api/scenes/{s[0]}/copyedits/{aid}', json={'expected_revision': rev, 'proposal_fingerprint': pv['proposal_fingerprint'], 'selected_indices':[0]})
print('apply', code, json.dumps(r, ensure_ascii=False)[:300])
summary()
print('PROSE', call('get_scene_text', scene_id=s[0], material='prose')['text'])
