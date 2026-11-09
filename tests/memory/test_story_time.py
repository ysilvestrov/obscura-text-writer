from types import SimpleNamespace as NS
from storygen.memory.story_time import scene_start,day_change,comparison_scene


def sc(id,pos,cast,beats='',trashed=None):
    return NS(id=id,position=pos,character_ids=cast,beats=beats,trashed_at=trashed)


def test_scene_start_date_and_day_forms():
    assert scene_start('Початок: 12.03.2024, 22:00\n…')==('date:12.3.2024','22:00')
    assert scene_start('**Початок:** день 3, 07:15')==('day:3','07:15')
    assert scene_start('Day 2, 06:00')is None
    assert scene_start('Початок: day 4, 06:00')==('day:4','06:00')


def test_day_change_same_form_only():
    a=sc('a',0,['h'],'Початок: 01.01.2024, 22:00')
    for beats,expected in [('Початок: 02.01.2024, 08:00',True),('Початок: 01.01.2024, 23:00',False),('Початок: день 1, 08:00',False),('Без мітки',False)]:
        assert day_change([a],sc('b',1,['h'],beats),'h') is expected
    assert day_change([sc('a',0,['h'],'Без мітки')],sc('b',1,['h'],'Початок: 02.01.2024, 08:00'),'h') is False
    assert day_change([sc('a',0,['h'],'Початок: день 1, 08:00')],sc('b',1,['h'],'Початок: день 2, 08:00'),'h') is True


def test_day_change_skips_scenes_without_character():
    s1=sc('1',0,['h'],'Початок: день 1, 20:00');s2=sc('2',1,[],'Початок: день 2, 08:00');s3=sc('3',2,['h'],'Початок: день 2, 09:00')
    assert comparison_scene([s1,s2,s3],s3,'h') is s1
    assert day_change([s1,s2,s3],s3,'h') is True
    assert comparison_scene([s1],s1,'h') is None


def test_comparison_skips_trashed():
    s1=sc('1',0,['h'],'Початок: день 1, 20:00');s2=sc('2',1,['h'],'Початок: день 5, 08:00','t');s3=sc('3',2,['h'],'Початок: день 1, 21:00')
    assert comparison_scene([s1,s2,s3],s3,'h') is s1


def test_date_keys_are_canonical():
    from storygen.memory.story_time import day_key
    key=lambda beats:day_key(sc('x',0,['h'],beats))
    assert key('Початок: 1.3.2024, 20:00')==key('Початок: 01.03.2024, 21:00')==key('Початок: 1.3.24, 22:00')=='date:1.3.2024'
    assert key('Початок: 02.03.2024, 08:00')!=key('Початок: 01.03.2024, 08:00')
    assert key('Початок: 1.4.2024, 08:00')!=key('Початок: 1.3.2024, 08:00')
    a=sc('a',0,['h'],'Початок: 1.3.2024, 20:00')
    assert day_change([a],sc('b',1,['h'],'Початок: 01.03.24, 22:00'),'h') is False
    assert day_change([a],sc('b',1,['h'],'Початок: 02.03.2024, 08:00'),'h') is True
