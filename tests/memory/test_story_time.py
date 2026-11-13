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


# STORY-TIME-S01: relative marks, «невідомо», the flashback mark; legacy keys unchanged.
from storygen.memory.story_time import Moment, scene_moment, flashback_marked


def test_legacy_keys_are_unchanged():
    assert scene_start('Початок: 12.03.2024, 22:00') == ('date:12.3.2024', '22:00')
    assert scene_start('Початок: 1.3.24, 08:00') == ('date:1.3.2024', '08:00')
    assert scene_start('**Початок:** день 3, 07:15') == ('day:3', '07:15')
    assert scene_start('Start: day 4, 06:00') == ('day:4', '06:00')


def test_relative_forms_in_any_order():
    assert scene_moment('Початок: Рік 2, День 14, 08:00') == Moment('rel', (2, 0, 14), 480, False)
    assert scene_moment('Початок: День 14 Рік 2') == Moment('rel', (2, 0, 14), None, False)
    assert scene_moment('Start: Year -20, Month 3') == Moment('rel', (-20, 3, 0), None, False)
    assert scene_start('Початок: Рік 2, Місяць 1, День 14') == ('rel:2.1.14', None)


def test_day_only_keeps_the_day_key():
    assert scene_start('Початок: день 3') == ('day:3', None)
    assert scene_moment('Початок: День -2, 23:30') == Moment('rel', (0, 0, -2), 1410, True)


def test_unknown_and_flashback_marks():
    assert scene_moment('Початок: невідомо') == Moment('unknown', None, None, False)
    assert scene_start('Start: unknown') is None
    assert scene_moment('Початок: (спогад)') is None and flashback_marked('Початок: (спогад)')
    assert scene_start('Початок: 01.03.2024, 08:00 (флешбек)') == ('date:1.3.2024', '08:00')
    assert flashback_marked('Start: Year -5 (Flashback)') and not flashback_marked('Початок: Рік 1')


def test_malformed_lines_are_not_moments():
    for line in ('Початок: Рік 1, Рік 2', 'Початок: Рік 1 вечір', 'Початок: 32 грудня', 'Day 2, 06:00'):
        assert scene_moment(line) is None and scene_start(line) is None


# STORY-TIME-S02: order of moments; day labels and the day change across mark forms.
from storygen.memory.story_time import before, day_label, scene_moment as m


def test_before_compares_one_kind_only():
    assert before(m('Початок: Рік -20'), m('Початок: Рік 1, День 3')) is True
    assert before(m('Початок: День 30'), m('Початок: Рік 1')) is True
    assert before(m('Початок: Рік 1, День 3'), m('Початок: Рік 1, День 3')) is False
    assert before(m('Початок: 01.03.2024, 08:00'), m('Початок: Рік 1')) is None
    assert before(m('Початок: невідомо'), m('Початок: Рік 1')) is None and before(None, m('Початок: Рік 1')) is None
    assert before(m('Початок: День 3, 08:00'), m('Початок: День 3, 09:00')) is True
    assert before(m('Початок: День 3'), m('Початок: День 3, 09:00')) is None


def test_relative_day_label():
    assert day_label('rel:2.0.14', 'uk') == 'рік 2, день 14' and day_label('rel:2.0.14', 'en') == 'year 2, day 14'
    assert day_label('rel:-20.3.0', 'uk') == 'рік -20, місяць 3'
    assert day_label('day:3', 'uk') == 'день 3' and day_label('date:1.3.2024', 'uk') == '1.3.2024'


def test_day_change_between_day_and_relative_forms():
    a = sc('a', 0, ['h'], 'Початок: Рік 0, День 2')
    assert day_change([a], sc('b', 1, ['h'], 'Початок: день 3, 08:00'), 'h') is True
    assert day_change([a], sc('b', 1, ['h'], 'Початок: День 2, 23:00'), 'h') is False
    assert day_change([a], sc('b', 1, ['h'], 'Початок: невідомо'), 'h') is False
    assert day_change([a], sc('b', 1, ['h'], 'Початок: 02.01.2024, 08:00'), 'h') is False
