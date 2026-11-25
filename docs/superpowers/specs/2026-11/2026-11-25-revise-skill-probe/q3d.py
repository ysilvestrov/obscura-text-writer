from ob import *
import re
o = call('create_story', title='Дайджест проба', language='uk', target_words=5000, writing_mode='chat'); oid=o['id']
st = call('get_story', story_id=oid); call('update_story', story_id=oid, expected_revision=st['revision'], content_rating={'sexual':0,'violence':0,'themes':0})
plan = '# План\n\nРобоча назва: Д\n\n## Сцена 1: А\nЛокація: вокзал\nХто бере участь: Олена\nЩо відбувається: приїзд.\n\n## Сцена 2: Б\nЛокація: дім\nХто бере участь: Олена\nЩо відбувається: вдома.\n'
call('import_plan_and_characters', story_id=oid, plan_markdown=plan, characters_markdown='# Персонажі\n\n## Олена\nРоль у творі: Головна героїня.\nВік: 34\n')
json.dump({'sid': oid}, open('state.json','w'))
s = scenes()
P1 = 'Олена приїхала потягом до Житомира.\n\nНа пероні пахло дощем і кавою.'
P2 = 'Олена відімкнула двері будинку.'
def full(sc, text, fact):
    do_brief(sc, 'x'); do_draft(sc, text)
    t = call('get_stage_task', scene_id=sc, stage='edit'); r = call('save_stage_result', scene_id=sc, stage='edit', task_fingerprint=t['task_fingerprint'], result=text)
    assert 'ERROR' not in r, r
    r = do_memory(sc, [fact]); assert 'ERROR' not in r, r
full(s[0], P1, 'Олена приїхала потягом до Житомира.')
full(s[1], P2, 'Олена відімкнула двері будинку.')
summary()
def mem2(): return call('get_scene_text', scene_id=s[1], material='memory')['version_id']
def revise(text, fact):
    do_draft(s[0], text)
    t = call('get_stage_task', scene_id=s[0], stage='edit'); r = call('save_stage_result', scene_id=s[0], stage='edit', task_fingerprint=t['task_fingerprint'], result=text); assert 'ERROR' not in r, r
    t = call('get_stage_task', scene_id=s[0], stage='memory'); print('  frags:', re.findall(r'\[(f\d+)\]', t['material']))
    r = do_memory(s[0], [fact]); assert 'ERROR' not in r, r
print('== A: change in f000002 only (fact cites f000001), identical claim text')
m0 = mem2(); runs0 = len(http('GET', f'/api/stories/{sid()}/runs')[1]['runs'])
revise('Олена приїхала потягом до Житомира.\n\nНа пероні пахло снігом і кавою.', 'Олена приїхала потягом до Житомира.')
summary(); print('  scene2 memory version changed:', mem2()!=m0, '| new runs:', len(http('GET', f'/api/stories/{sid()}/runs')[1]['runs'])-runs0)
print('== B: change inside f000001 (quoted), identical claim text')
m0 = mem2(); runs0 = len(http('GET', f'/api/stories/{sid()}/runs')[1]['runs'])
revise('Олена приїхала нічним потягом до Житомира.\n\nНа пероні пахло снігом і кавою.', 'Олена приїхала потягом до Житомира.')
summary(); print('  scene2 memory version changed:', mem2()!=m0, '| new runs:', len(http('GET', f'/api/stories/{sid()}/runs')[1]['runs'])-runs0)
print('  MEM1', call('get_scene_text', scene_id=s[0], material='memory')['text'])
