from ob import *
s = scenes()
code, d = http('GET', f'/api/stories/{sid()}')
sc = [x for x in d['scenes'] if x['id']==s[1]][0]
ph = sc['heads']['prose']
code, pv = http('GET', f'/api/scenes/{s[1]}/acceptance-preview', params={'version_id': ph})
print('preview', code, {k:v for k,v in pv.items() if k!='text'} if isinstance(pv, dict) else pv)
code, r = http('POST', f'/api/scenes/{s[1]}/accept-version', json={'version_id': ph, 'expected_revision': pv['expected_revision'], 'preview_fingerprint': pv['preview_fingerprint']})
print('accept', code, json.dumps(r, ensure_ascii=False)[:600])
summary()
code, d = http('GET', f'/api/stories/{sid()}')
print('s2 ms', json.dumps(d['material_status'][s[1]], ensure_ascii=False))
print('story prose-acceptance GET', http('GET', f'/api/stories/{sid()}/prose-acceptance'))
