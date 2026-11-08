"""In-memory SceneInput builders for strategy and metric tests (no database)."""
from memory_bench.model import Record, SceneInput

NAMES={'c1':'Марія','c2':'Остап','c3':'Ганна'}


def rec(claim,category,text,chars=(),scene=1,changed=None,kind=None):
    return Record(claim,category,text,tuple(chars),scene,changed if changed is not None else scene,kind)


def scene(records=(),timeline=(),cast=('c1',),protagonist='c1',id='s10',number=10,plan='',prose='',targets=()):
    return SceneInput(id,number,tuple(cast),plan,prose,tuple(records),tuple(timeline),protagonist,NAMES,frozenset(targets),0)


def rich_records():
    out=[rec('core1','character_states','Марія в халаті',['c1'],9),
         rec('core_old','character_states','Марія любить каву',['c1'],2),
         rec('pres1','character_states','Остап втомлений',['c2'],8),
         rec('absent','character_states','Ганна в місті',['c3'],8),
         rec('gen1','character_states','Іде дощ'),
         rec('thr1','open_threads','Остап шукає ключ'),
         rec('thr_far','open_threads','Хтось бачив вовка'),
         rec('fact1','facts','Остапа звуть сусідом'),
         rec('fact_hero','facts','Марія колись жила біля моря'),
         rec('fact_far','facts','Маяк стоїть на скелі')]
    out+=[rec(f'filler{i}','facts',f'Маяк і море номер {i} '+'слово '*20) for i in range(30)]
    return out
