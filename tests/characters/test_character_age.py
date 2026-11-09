import pytest
from storygen.characters.models import CharacterEntry,CharacterRecord
from storygen.domain import Scene


@pytest.mark.parametrize('value,expected',[
    ('27.','adult'),('17','minor'),('на вигляд 16, насправді 300','minor'),('18-20','adult'),
    ('Дорослий.','adult'),(' доросла ','adult'),('adult','adult'),
    ('ще не дорослий','unknown'),('not an adult','unknown'),('майже доросла','unknown'),
    ('','unknown'),('невідомо','unknown'),
    ('** Дорослий','adult'),('_доросла_','adult'),('**34**','adult'),('** 15','minor'),
    ('_ще не дорослий_','unknown'),('**','unknown')])
def test_parse_age_value(value,expected):
    from storygen.characters.age import parse_age_value
    assert parse_age_value(value)==expected


@pytest.mark.parametrize('text,expected',[
    ('Вік:\nЗріст: 160 см.','unknown'),('Зовнішність: висока.\nВік: 34.','adult'),
    ('- **Вік:** 15','minor'),('Чоловік: Петро',None),('Age: 40','adult'),
    ('- **Вік:** Дорослий','adult'),('Вік: _доросла_','adult'),('Вік: **34**','adult'),
    ('**Вік**: 34','adult'),('__Age__: 12','minor'),('**Чоловік**: Петро',None),
    ('Вік: 16\r\nВік: 30','minor'),('Вік: 30\rВік: 16','minor'),('Вік: 16\r\n','minor'),
    ('Вік: 30\nВік: 16','minor'),('Вік: 30\nВік: невідомо','unknown'),('Без віку',None)])
def test_entry_age(text,expected):
    from storygen.characters.age import entry_age
    assert entry_age(text)==expected


def entry(id,text,availability='timeless',anchor=None):
    return CharacterEntry(id=id,text=text,availability=availability,available_from_scene_id=anchor,origin='author')


def card(id,*entries):
    return CharacterRecord(id=id,name='N'+id,entries=list(entries))


def scenes(ids=('A',)):
    return [Scene(id=str(i),story_id='story',title=str(i),position=i,character_ids=list(ids)) for i in range(1,4)]


def test_no_age_line_is_unknown():
    from storygen.characters.age import scene_ages
    assert scene_ages([card('A',entry('e','Висока.'))],scenes(),'1')=={'A':'unknown'}
    assert scene_ages([card('A')],scenes(),'1')=={'A':'unknown'}


def test_from_scene_overrides_timeless_after_anchor():
    from storygen.characters.age import scene_ages
    cards=[card('A',entry('t','Вік: 17'),entry('f','Вік: 18','from_scene','2'))]
    assert scene_ages(cards,scenes(),'3')=={'A':'adult'}
    assert scene_ages(cards,scenes(),'2')=={'A':'adult'}
    assert scene_ages(cards,scenes(),'1')=={'A':'minor'}


def test_worst_verdict_among_timeless():
    from storygen.characters.age import scene_ages
    cards=[card('A',entry('a','Вік: 30'),entry('b','Вік: 16'))]
    assert scene_ages(cards,scenes(),'1')=={'A':'minor'}
    cards=[card('A',entry('a','Вік: 30'),entry('b','Вік: ?'))]
    assert scene_ages(cards,scenes(),'1')=={'A':'unknown'}


def test_missing_card_is_unknown_and_each_participant_reported():
    from storygen.characters.age import scene_ages
    cards=[card('A',entry('a','Вік: 30'))]
    assert scene_ages(cards,scenes(('A','B')),'1')=={'A':'adult','B':'unknown'}


def test_later_anchor_ignored_and_bad_anchor_skipped():
    from storygen.characters.age import scene_ages
    cards=[card('A',entry('a','Вік: 30'),entry('f','Вік: 10','from_scene','3'),entry('g','Вік: 10','from_scene','nope'))]
    assert scene_ages(cards,scenes(),'2')=={'A':'adult'}


def test_latest_anchor_group_wins_and_trashed_anchor_skipped():
    from storygen.characters.age import scene_ages
    sc=scenes()
    cards=[card('A',entry('a','Вік: 10','from_scene','1'),entry('b','Вік: 20','from_scene','2'))]
    assert scene_ages(cards,sc,'3')=={'A':'adult'}
    sc[1].trashed_at='x'
    assert scene_ages(cards,sc,'3')=={'A':'minor'}


def test_other_story_anchor_skipped():
    from storygen.characters.age import scene_ages
    sc=scenes()+[Scene(id='x',story_id='other',title='x',position=0)]
    cards=[card('A',entry('a','Вік: 30'),entry('b','Вік: 10','from_scene','x'))]
    assert scene_ages(cards,sc,'1')=={'A':'adult'}
