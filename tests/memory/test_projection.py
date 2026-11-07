import json


def test_projection_is_deterministic_and_excludes_proof_metadata():
    from storygen.memory.journal import load_memory
    from storygen.memory.projection import project_memory, memory_catalog
    quote='Дуже довге дослівне підтвердження з оригінальної прози.'
    memory=load_memory(json.dumps({'facts':[{'text':'Ключ у сейфі','source_version_id':'secret-version-id','quote':quote}],
        'source_prose_ids':['secret-version-id']}))
    first=project_memory(memory,[],{'secret-version-id':1})
    assert first==project_memory(memory,[],{'secret-version-id':1})
    assert 'Ключ у сейфі' in first.text
    for technical in [quote,'secret-version-id','source_version_id',memory.events[0].claim_id]:
        assert technical not in first.text
    assert quote not in memory_catalog(memory)
    assert first.metrics['event_count']==1


def test_projection_filters_only_scoped_states_and_keeps_closed_thread_history():
    from storygen.memory.journal import MemoryJournal, MemoryEvent
    from storygen.memory.projection import project_memory
    def event(id,category,text,characters=(),op='add',claim=None):
        return MemoryEvent(event_id=id,claim_id=claim or id,operation=op,category=category,
            text=text,character_ids=list(characters),source_version_id='p',quote='доказ')
    memory=MemoryJournal(source_prose_ids=['p'],events=[
        event('a','character_states','Стан A',['A']),event('b','character_states','Стан B',['B']),
        event('g','character_states','Загальний стан'),event('t','open_threads','Пошук ключа'),
        event('r','open_threads','Ключ знайдено',op='retire',claim='t')])
    selected=project_memory(memory,['A'],{'p':1})
    assert 'Стан A' in selected.text and 'Стан B' not in selected.text
    assert 'Загальний стан' in selected.text and 'Ключ знайдено' in selected.text
    assert 'Пошук ключа' not in selected.text
    assert selected.metrics['omitted_state_count']==1
    assert 'Стан B' in project_memory(memory,[],{'p':1}).text


def test_catalog_v3_hides_immutable_ids():
    from storygen.memory.journal import MemoryJournal, MemoryEvent
    from storygen.memory.projection import memory_catalog_v3
    def event(id,category,text,characters=()):
        return MemoryEvent(event_id='e'+id,claim_id=id,operation='add',category=category,
            text=text,character_ids=list(characters),source_version_id='p',quote='доказ')
    journal=MemoryJournal(source_prose_ids=['p'],events=[event('mc_fact','facts','Текст факту'),
        event('mc_state','character_states','Стан A',['A']),event('mc_thread','open_threads','Лінія')])
    text=memory_catalog_v3(journal)
    assert 'mc_fact' not in text and 'mc_state' in text and 'Текст факту' in text and 'доказ' not in text
    data=json.loads(text)
    assert data['mutable']==[{'claim_id':'mc_state','category':'character_states','text':'Стан A','character_ids':['A']},
        {'claim_id':'mc_thread','category':'open_threads','text':'Лінія','character_ids':[]}]
    assert data['immutable']==[{'category':'facts','text':'Текст факту'}]
    assert ': ' not in text and ', ' not in text
