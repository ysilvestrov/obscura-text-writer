from ob import *
s = scenes()
st = call('get_settings', story_id=sid())
p(call('update_settings', story_id=sid(), section='editor', expected_fingerprint=st['roles']['editor']['fingerprint'], fields={'context_tokens':128000,'max_output_tokens':8000})['changed'])
t = call('get_stage_task', scene_id=s[0], stage='edit')
print('result_format', t['result_format'])
print('INSTR', t['instructions'][:2500])
