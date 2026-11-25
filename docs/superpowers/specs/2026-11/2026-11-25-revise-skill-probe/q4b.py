from ob import *
s = scenes()
code, r = http('GET', f'/api/scenes/{s[0]}/copyedits'); print(code, json.dumps(r, ensure_ascii=False)[:1500])
