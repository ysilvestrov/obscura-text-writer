from ob import *
s = scenes()
chars = '# Персонажі\n\n## Олена\nРоль у творі: Головна героїня.\nВік: 34\nЗовнішність: руде волосся, зелений плащ.\nЗаняття та навички: перекладачка.\n'
r = call('import_plan_and_characters', story_id=sid(), characters_markdown=chars); print(json.dumps(r, ensure_ascii=False)[:1200])
c = call('get_scene_context', scene_id=s[1]); txt = json.dumps(c['characters'], ensure_ascii=False)
print('card has руде:', 'руде' in txt, '| still сірий:', 'сірий' in txt); print(txt[:600])
summary()
