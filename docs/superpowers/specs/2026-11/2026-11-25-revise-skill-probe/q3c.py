from ob import *
s = scenes()
for link in ('brief','prose'):
    code, d = http('GET', f'/api/stories/{sid()}')
    fp = d['material_status'][s[1]]['links'][link]['fingerprint']
    print(link, http('POST', f'/api/scenes/{s[1]}/links/{link}/decision', json={'action':'approve','fingerprint':fp}))
summary()
