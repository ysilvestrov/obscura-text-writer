import json
import pytest
from storygen.domain import Scene


def scenes():
    return [Scene(id=str(i),story_id='story',title=str(i),position=i,character_ids=['A']) for i in range(3)]


def cards():
    from storygen.characters.models import load_characters
    return load_characters(json.dumps([{'schema_version':2,'id':'A','name':'Анна','entries':[
        {'id':'known','text':'Фотографка','availability':'timeless','available_from_scene_id':None,'origin':'author','sources':[]},
        {'id':'future','text':'ТАЄМНИЦЯ ФІНАЛУ','availability':'from_scene','available_from_scene_id':'2','origin':'author','sources':[]},
        {'id':'unknown','text':'Непозначений опис','availability':'unclassified','available_from_scene_id':None,'origin':'author','sources':[]}]}]))


def test_future_fact_excluded_until_its_stable_scene_and_unknown_warns():
    from storygen.characters.projection import project_characters
    for index in (0,1,2):
        result=project_characters(cards(),scenes(),str(index))
        assert ('ТАЄМНИЦЯ ФІНАЛУ' in result.text)==(index==2)
        assert 'Фотографка' in result.text and result.warnings
        assert ('future' in result.included_entry_ids)==(index==2)
    reordered=scenes();reordered[2].position=0;reordered[0].position=1;reordered[1].position=2
    assert 'ТАЄМНИЦЯ ФІНАЛУ' in project_characters(cards(),reordered,'0').text


def test_empty_projection_never_falls_back_and_bad_anchor_rejects():
    from storygen.characters.projection import project_characters
    value=cards();value[0].entries=value[0].entries[1:2]
    assert 'ТАЄМНИЦЯ ФІНАЛУ' not in project_characters(value,scenes(),'0').text
    removed=scenes()[:2]
    with pytest.raises(ValueError):project_characters(value,removed,'0')
    only_b=scenes();only_b[0].character_ids=['B']
    assert 'ТАЄМНИЦЯ ФІНАЛУ' not in project_characters(value,only_b,'0').text
