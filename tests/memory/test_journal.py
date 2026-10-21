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
