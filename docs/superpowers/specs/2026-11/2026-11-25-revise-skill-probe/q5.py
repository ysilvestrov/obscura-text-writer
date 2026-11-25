from ob import *
s = scenes()
pl = call('get_scene_text', scene_id=s[0], material='plan')
c = call('get_scene_context', scene_id=s[0])
newplan = pl['text'].replace('Житомир', 'Київ')
r = call('update_scene', story_id=sid(), scene_id=s[0], expected_revision=c['revision'], plan_markdown=newplan, plan_version_id=pl['version_id']); p(r)
summary()
# obscura story
o = call('create_story', title='Обскура проба', language='uk', target_words=5000, writing_mode='obscura'); p(o)
oid = o['id']
plan = '''# План

Робоча назва: Обскура проба

## Сцена 1: Вокзал
Локація: вокзал у Житомирі
Хто бере участь: Олена
Що відбувається: Олена приїздить.

## Сцена 2: Дім
Локація: дім
Хто бере участь: Олена
Що відбувається: Олена вдома.
'''
chars = '# Персонажі\n\n## Олена\nРоль у творі: Головна героїня.\nВік: 34\n'
call('import_plan_and_characters', story_id=oid, plan_markdown=plan, characters_markdown=chars)
st = call('get_story', story_id=oid); os1 = st['scenes'][0]['id']; print('obscura mode', st['writing_mode'])
pl = call('get_scene_text', scene_id=os1, material='plan')
r = call('update_scene', story_id=oid, scene_id=os1, expected_revision=st['scenes'][0]['revision'], plan_markdown=pl['text'].replace('Житомир','Київ'), plan_version_id=pl['version_id']); p(r)
c = call('get_scene_context', scene_id=os1)
if 'ERROR' in c: p(c)
d = call('get_scene_text', scene_id=os1, material='draft')
r = call('save_draft', scene_id=os1, text='Олена вийшла з потяга.', expected_revision=c.get('revision', 0), context_fingerprint=c.get('context_fingerprint','0'*64), draft_version_id=d.get('version_id')); p(r)
for stage in ('brief','edit','memory'):
    t = call('get_stage_task', scene_id=os1, stage=stage); print(stage, 'task:', t.get('ERROR') or ('ok fp '+t['task_fingerprint'][:8]))
t = call('get_stage_task', scene_id=os1, stage='brief')
if 'task_fingerprint' in t:
    r = call('save_stage_result', scene_id=os1, stage='brief', task_fingerprint=t['task_fingerprint'], result={'objective':'x','beats':['a'],'constraints':[],'proposed_changes':[],'introduced':[]}); p(r)
p(call('start_run', story_id=oid, action='draft', scene_id=os1), 1200)
