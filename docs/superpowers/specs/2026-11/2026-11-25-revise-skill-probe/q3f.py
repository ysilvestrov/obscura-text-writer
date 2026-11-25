from ob import *
s = scenes()
for link in ('brief','prose'):
    fp = http('GET', f'/api/stories/{sid()}')[1]['material_status'][s[1]]['links'][link]['fingerprint']
    http('POST', f'/api/scenes/{s[1]}/links/{link}/decision', json={'action':'approve','fingerprint':fp})
summary()
before = call('get_scene_text', scene_id=s[0], material='memory')
r = do_memory(s[0], ['Олена приїхала потягом до Житомира.']); print('redo same memory:', r)
after = call('get_scene_text', scene_id=s[0], material='memory')
print('claim_id before/after', json.loads(before['text'])[0]['claim_id'], json.loads(after['text'])[0]['claim_id'], 'version', before['version_id']!=after['version_id'])
summary()
