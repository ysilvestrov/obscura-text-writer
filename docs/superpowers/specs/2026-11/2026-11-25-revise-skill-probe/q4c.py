from ob import *
s = scenes()
aid = http('GET', f'/api/scenes/{s[0]}/copyedits')[1]['attempts'][0]['id']
code, pv = http('GET', f'/api/scenes/{s[0]}/copyedits/{aid}'); print(code, json.dumps(pv, ensure_ascii=False)[:1200])
if code == 200:
    rev = call('get_scene_context', scene_id=s[0])['revision']
    code, r = http('POST', f'/api/scenes/{s[0]}/copyedits/{aid}', json={'expected_revision': rev, 'proposal_fingerprint': pv.get('proposal_fingerprint',''), 'selected_indices':[0]})
    print('apply', code, json.dumps(r, ensure_ascii=False)[:800])
summary()
