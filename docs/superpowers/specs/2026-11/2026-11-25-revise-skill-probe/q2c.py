from ob import *
r = call('get_settings', story_id=sid(), section='editor') if True else None
p(r, 3000)
