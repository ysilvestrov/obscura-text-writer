from ob import *
s = scenes()
print('RUNS before', http('GET', f'/api/stories/{sid()}/runs'))
r = do_draft(s[0], 'Олена вийшла з потяга на вокзалі у Вінниці. Над пероном висів старий годинник, і стрілки стояли на десятій. Місто здавалося меншим, ніж вона пам’ятала. Вона поправила сірий плащ і пішла до будинку.')
p(r)
summary()
for i in (0,1):
    st = stale(s[i])
    print('scene', i+1, {m: (v.get('version_id'), 'stale=', v.get('stale'), v.get('kind')) for m,v in st.items()})
print('RUNS after', http('GET', f'/api/stories/{sid()}/runs'))
