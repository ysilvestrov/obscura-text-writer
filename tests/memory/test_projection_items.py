from storygen.memory.journal import MemoryEvent,MemoryJournal
from storygen.memory.projection import memory_items,project_memory,render_memory


def ev(id,category,text,*,op='add',claim=None,chars=(),slot=None,kind='prose',quote='доказ',resolves=None,source='p1'):
    return MemoryEvent(event_id='e'+id,claim_id=claim or id,operation=op,category=category,text=text,character_ids=list(chars),
        source_version_id=source,quote=quote,slot=slot,source_kind=kind,resolves_claim_id=resolves)


def rich_journal():
    return MemoryJournal(schema_version=3,source_prose_ids=['p1','p2'],events=[
        ev('loc','character_states','Квартира на Подолі',chars=['h'],slot='location'),
        ev('car','character_states','Пістолет у сумці',chars=['h'],slot='carried',kind='author',quote=None),
        ev('mood','character_states','Ганна втомлена',chars=['h']),
        ev('away','character_states','Петро в Києві',chars=['x']),
        ev('ola','character_states','Оля сердиться',chars=['a']),
        ev('rain','character_states','Іде дощ'),
        ev('t1','open_threads','Хто вкрав ключ'),
        ev('t2','open_threads','Лист без підпису'),
        ev('t3','open_threads','Борг Олі'),
        ev('f1','facts','Ключ у сейфі'),
        ev('secret','facts','Прихований факт'),
        ev('tl1','timeline','Ганна приїхала'),
        ev('t2r','open_threads','Лист без підпису',op='retire',claim='t2',source='p2'),
        ev('t3r','open_threads','Борг Олі',op='retire',claim='t3',source='p2'),
        ev('f2','facts','Оля віддала борг',resolves='t3',source='p2'),
        ev('mood2','character_states','Ганна спокійна',op='update',claim='mood',chars=['h'],source='p2'),
        ev('tl2','timeline','Ганна знайшла лист',source='p2')])


# The literal is the output of project_memory before it was split into memory_items/render_memory (#60): the split is like-for-like.
EXPECTED='''ЯДРО СТАНУ — Ганна
при собі: Пістолет у сумці (читачеві невідомо: якщо знадобиться, введи в тексті як нове)
місце: Квартира на Подолі

ФАКТИ
— Ключ у сейфі
— Оля віддала борг

ПОТОЧНІ СТАНИ
— Ганна спокійна
— Оля сердиться
— Іде дощ

ВІДКРИТІ ЛІНІЇ
— Хто вкрав ключ

ХРОНОЛОГІЯ
— Сцена 1: Ганна приїхала
— Сцена 2: Лист без підпису
— Сцена 2: Ганна знайшла лист'''


def test_split_projection_is_byte_identical():
    result=project_memory(rich_journal(),['h','a'],{'p1':1,'p2':2},hidden_claim_ids=['secret'],tracked=['h'],names={'h':'Ганна'})
    assert result.text==EXPECTED
    assert result.metrics['omitted_state_count']==1 and result.metrics['core_line_count']==2 and result.metrics['hidden_claim_count']==1


def test_items_carry_sections_and_sources():
    items,_=memory_items(rich_journal(),['h','a'],{'p1':1,'p2':2},hidden_claim_ids=['secret'],tracked=['h'],names={'h':'Ганна'})
    assert render_memory(items,['h'],{'h':'Ганна'})==EXPECTED
    by={i.claim_id:i for i in items}
    assert by['loc'].section=='core' and by['loc'].owner=='h' and by['loc'].slot=='location'
    assert by['mood'].source_scene==2 and by['mood'].character_ids==('h',)
    assert by['t2'].section=='timeline' and by['t2'].source_scene==2
    assert 'away' not in by and 'secret' not in by


def test_timeline_note_goes_first_in_timeline():
    text=render_memory([],[],timeline_note='Не показано записів: 3 (сцени 1–3).')
    assert text.endswith('ХРОНОЛОГІЯ\n— Не показано записів: 3 (сцени 1–3).')
