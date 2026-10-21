import json
import pytest


def test_legacy_card_becomes_stable_unclassified_without_rewriting_text():
    from storygen.characters.models import load_characters
    raw=json.dumps([{'id':'A','name':'Анна','description':'Знайомиться з B у фіналі.',
        'sources':[{'version_id':'source','quote':'Анна'}]}])
    first=load_characters(raw)
    assert first==load_characters(raw)
    assert first[0].entries[0].availability=='unclassified'
    assert first[0].entries[0].text=='Знайомиться з B у фіналі.'


@pytest.mark.parametrize('changes',[
    {'availability':'from_scene','available_from_scene_id':None},
    {'availability':'timeless','available_from_scene_id':'scene'},
    {'origin':'imported','sources':[]},
    {'text':' '},
])
def test_invalid_temporal_entry_rejected(changes):
    from storygen.characters.models import CharacterEntry
    value={'id':'entry','text':'Факт','availability':'unclassified',
        'available_from_scene_id':None,'origin':'author','sources':[]}
    value.update(changes)
    with pytest.raises(ValueError):CharacterEntry.model_validate(value)
