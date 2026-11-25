from ob import *
s = scenes()
c = call('get_scene_context', scene_id=s[0]); txt = json.dumps(c.get('characters', c), ensure_ascii=False)
print('card has руде:', 'руде' in txt, '| still сірий:', 'сірий' in txt)
