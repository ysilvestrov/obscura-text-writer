from types import SimpleNamespace
import pytest
from storygen.characters.models import CharacterRecord
from storygen.characters.acquaintance import is_protagonist_line,known_names_line,protagonist,pre_story_known


def card(cid,name,*texts,availability='timeless',anchor=None):
    entries=[dict(id=f'{cid}{i}',text=text,availability=availability,available_from_scene_id=anchor,origin='author') for i,text in enumerate(texts)]
    return CharacterRecord.model_validate(dict(schema_version=2,id=cid,name=name,entries=entries))


def scene(sid,position,cast=(),trashed=None):
    return SimpleNamespace(id=sid,story_id='s',position=position,character_ids=list(cast),trashed_at=trashed)


def test_protagonist_line_variants():
    for line in ['Протагоніст','**Головний герой.**','- головна героїня:','— Протагоністка!']:
        assert is_protagonist_line(line)
    assert not is_protagonist_line('Протагоніст іншої історії')


def test_known_names_line_parses_and_ignores_other_lines():
    assert known_names_line('Знайомий з: Анна, Богдан (сусід; давно)')==['Анна','Богдан (сусід; давно)']
    assert known_names_line('**знайм з:** Віра')==['Віра']
    assert known_names_line('Вік: 30.') is None


def test_protagonist_marker_beats_first_cast_and_warns_on_duplicates():
    cards=[card('A','Анна','Вік: 30'),card('B','Богдан','Протагоніст'),card('C','Віра','- Головна героїня')]
    hero,warnings=protagonist(cards,[scene('1',0,['A','B'])])
    assert hero=='B' and len(warnings)==1
    assert 'Богдан' not in warnings[0] and 'Віра' not in warnings[0]


def test_protagonist_defaults_to_first_of_earliest_nonempty_cast():
    cards=[card('A','Анна','x'),card('C','Віра','y')]
    scenes=[scene('0',0,[]),scene('1',1,['C','A']),scene('t',-1,['A'],trashed='now'),scene('2',2,['A'])]
    assert protagonist(cards,scenes)==('C',[])
    assert protagonist(cards,[])==(None,[])


def test_protagonist_marker_ignores_availability():
    cards=[card('A','Анна','Протагоніст',availability='from_scene',anchor='3'),card('B','Богдан','x')]
    scenes=[scene('1',1,['B']),scene('3',3,['A'])]
    assert protagonist(cards,scenes)==('A',[])


def test_pre_story_known_is_symmetric_and_respects_availability():
    cards=[card('A','Анна','x'),card('B','Богдан','Знайомий з: Анна'),
        card('C','Віра','Знайомий з: Анна',availability='from_scene',anchor='4'),
        card('D','Галина','y')]
    scenes=[scene('2',2),scene('4',4)]
    assert pre_story_known(cards,scenes,'2','A')==({'B'},[])
    assert pre_story_known(cards,scenes,'4','A')==({'B','C'},[])
    cards[0]=card('A','Анна','Знайомий з: Галина')
    assert pre_story_known(cards,scenes,'2','A')==({'B','D'},[])


def test_unknown_known_name_warns_without_blocking():
    cards=[card('A','Анна','Знайомий з: Невідомий'),card('B','Богдан','x')]
    known,warnings=pre_story_known(cards,[scene('1',1)],'1','A')
    assert known==set() and len(warnings)==1 and 'Невідомий' not in ' '.join(warnings)


def test_bad_anchor_raises():
    cards=[card('A','Анна','Знайомий з: Богдан',availability='from_scene',anchor='gone')]
    with pytest.raises(ValueError):pre_story_known(cards,[scene('1',1)],'1','A')


def test_italic_markers_recognised():
    assert is_protagonist_line('*Протагоніст*')
    assert is_protagonist_line('*Головна героїня.*')
    assert known_names_line('*Знайомий з: Анна*')==['Анна']


def test_unrelated_card_with_bad_anchor_does_not_abort():
    cards=[card('A','Анна','x'),card('B','Богдан','Знайомий з: Анна'),
        card('C','Віра','без позначок',availability='from_scene',anchor='gone')]
    assert pre_story_known(cards,[scene('1',1)],'1','A')==({'B'},[])


def test_mid_line_italic_label_and_protagonist_colon():
    assert known_names_line('*Знайомий з:* Анна')==['Анна']
    assert known_names_line('*Знайомий з:* *Анна*, Богдан')==['Анна','Богдан']
    assert is_protagonist_line('*Протагоніст*:')
