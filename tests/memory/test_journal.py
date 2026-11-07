import json
import pytest


def legacy(entries=None):
    return json.dumps({'facts':entries or [],'character_states':[], 'open_threads':[],
        'timeline':[], 'source_prose_ids':['p1']},ensure_ascii=False)


def test_legacy_conversion_is_stable_and_preserves_prefix():
    from storygen.memory.journal import load_memory
    entry={'text':'Ключ у сейфі','source_version_id':'p1','quote':'ключ у сейфі'}
    first=load_memory(legacy([entry]))
    later=json.loads(legacy([entry]));later['source_prose_ids'].append('p2')
    later['facts'].append({'text':'Знайшли лист','source_version_id':'p2','quote':'лист'})
    assert load_memory(legacy([entry]))==first
    assert load_memory(json.dumps(later)).events[:1]==first.events
    assert first.events[0].quote==entry['quote']


def test_journal_rejects_duplicate_events_unknown_sources_and_invalid_update():
    from storygen.memory.journal import load_memory, MemoryJournal
    entry={'text':'Ключ у сейфі','source_version_id':'p1','quote':'ключ у сейфі'}
    base=load_memory(legacy([entry])).model_dump()
    duplicate={**base,'events':base['events']*2}
    with pytest.raises(ValueError):MemoryJournal.model_validate(duplicate)
    bad={**base,'source_prose_ids':['p2']}
    with pytest.raises(ValueError):MemoryJournal.model_validate(bad)
    event={**base['events'][0],'event_id':'new','operation':'update'}
    with pytest.raises(ValueError):MemoryJournal.model_validate({**base,'events':base['events']+[event]})


def test_unknown_or_mixed_version_does_not_fall_back():
    from storygen.memory.journal import load_memory
    with pytest.raises(ValueError):load_memory('{"schema_version":3,"facts":[]}')
    with pytest.raises(ValueError):load_memory('{"schema_version":2,"events":[],"source_prose_ids":[],"facts":[]}')


def test_supporting_quotes_default_keeps_v2_ids():
    from storygen.memory.journal import _add_event, stable_id
    a=_add_event('facts','Т','p1','рядок',0)
    b=_add_event('facts','Т','p1','рядок',0,supporting=())
    assert a.supporting_quotes==[] and a.claim_id==b.claim_id
    assert a.claim_id==stable_id('mc_',['facts','Т','p1','рядок',0])


def test_supporting_quotes_change_ids_and_are_capped():
    from pydantic import ValidationError
    from storygen.memory.journal import _add_event, MemoryEvent
    a=_add_event('facts','Т','p1','рядок',0,supporting=('інший',))
    assert a.supporting_quotes==['інший'] and a.claim_id!=_add_event('facts','Т','p1','рядок',0).claim_id
    with pytest.raises(ValidationError):
        MemoryEvent(**{**a.model_dump(),'supporting_quotes':['x','y','z']})
    with pytest.raises(ValidationError):
        MemoryEvent(**{**a.model_dump(),'supporting_quotes':[' ']})


def test_change_event_id_matches_v2_formula_and_depends_on_supporting():
    from storygen.memory.journal import change_event_id, stable_id
    assert change_event_id('update','c1','Т','p1','q')==stable_id('me_',['update','c1','Т','p1','q'])
    assert change_event_id('update','c1','Т','p1','q',('s',))!=change_event_id('update','c1','Т','p1','q')


def test_validate_journal_rejects_supporting_quote_not_in_source():
    from storygen.memory.journal import _add_event, MemoryJournal, validate_memory_journal
    ok=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Т','p1','рядок',0,supporting=('інший',))])
    assert validate_memory_journal(ok,{'p1':'рядок і інший'})
    with pytest.raises(ValueError,match='дослівного'):
        validate_memory_journal(ok,{'p1':'рядок'})
    bad=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Т','p1','рядок',0,supporting=('немає у прозі',))])
    with pytest.raises(ValueError,match='дослівного'):
        validate_memory_journal(bad,{'p1':'рядок'})


def test_old_journal_without_field_loads_unchanged():
    from storygen.memory.journal import load_memory, _add_event, MemoryJournal
    plain=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Т','p1','рядок',0)])
    raw=plain.model_dump_json()
    assert 'supporting_quotes' not in raw
    assert load_memory(raw).model_dump_json()==raw
    assert load_memory(raw).events[0].supporting_quotes==[]
    rich=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Т','p1','рядок',0,supporting=('інший',))])
    assert load_memory(rich.model_dump_json())==rich and '"supporting_quotes":["інший"]' in rich.model_dump_json()
