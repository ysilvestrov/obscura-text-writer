from ob import *
s = scenes()
summary()
code, d = http('GET', f'/api/stories/{sid()}')
print('s2 links', json.dumps(d['material_status'][s[1]], ensure_ascii=False))
for r in http('GET', f'/api/stories/{sid()}/runs')[1]['runs']: print(r['request']['mode'], r['state'], r['created_at'], r['request_id'])
