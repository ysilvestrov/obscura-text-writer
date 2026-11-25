"""Probe A: chat writes to scene 2 while its brief/prose links are unchecked (no author decision)."""
from ob import *
new_story('Проба A')
s = scenes()
def full(sc, text, fact, brief=True):
    if brief: print('  brief', do_brief(sc, 'x'))
    print('  draft', do_draft(sc, text))
    print('  edit', do_edit_same(sc))
    print('  memory', do_memory(sc, [fact]))
full(s[0], 'Олена приїхала до Житомира.', 'Олена приїхала до Житомира.')
full(s[1], 'Олена відімкнула двері.', 'Олена відімкнула двері.')
summary()
def break_scene2():
    do_draft(s[0], call('get_scene_text', scene_id=s[0], material='prose')['text'].replace('.', ' вранці.', 1))
    do_edit_same(s[0]); print('  s1 memory', do_memory(s[0], ['Олена приїхала до Житомира.'])); wait_runs()
print('== break scene 2'); break_scene2(); summary()
print('== A1: full cycle on scene 2 incl. brief')
full(s[1], 'Олена відімкнула двері ключем.', 'Олена відімкнула двері ключем.'); wait_runs(); summary()
print('== break scene 2 again'); break_scene2(); summary()
print('== A2: draft -> edit -> memory, no brief')
full(s[1], 'Олена відімкнула старі двері ключем.', 'Олена відімкнула старі двері ключем.', brief=False); wait_runs(); summary()
print('  s2 links', json.dumps(links(s[1])['links'], ensure_ascii=False))
