from ob import *
st = call('get_settings', story_id=sid())
fp = st['roles']['editor']['fingerprint']
r = call('update_settings', story_id=sid(), section='editor', expected_fingerprint=fp,
         fields={'provider':'local','model':'dummy','base_url':'http://127.0.0.1:9/v1','edit_mode':'patches','edit_review':'auto'})
p(r, 1500)
st = call('get_settings', story_id=sid()); p(st['roles']['editor'], 1500)
