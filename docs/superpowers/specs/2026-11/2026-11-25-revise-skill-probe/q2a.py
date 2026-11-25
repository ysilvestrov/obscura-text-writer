from ob import *
s = scenes()
code, d = http('GET', f'/api/stories/{sid()}')
ms = d['material_status'][s[0]]; p(ms, 3000)
sc = [x for x in d['scenes'] if x['id']==s[0]][0]; print('heads', sc.get('heads'), 'needs_review', sc.get('needs_review'))
print('PROSE', call('get_scene_text', scene_id=s[0], material='prose')['text'])
