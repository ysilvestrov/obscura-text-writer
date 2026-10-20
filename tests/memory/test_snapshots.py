import pytest
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.memory.service import validate_memory


def test_memory_facts_require_existing_source_quotes():
    snapshot=MemorySnapshot(facts=[MemoryEntry(text='Нова студія',source_version_id='prose1',quote='нова студія')],source_prose_ids=['prose1'])
    assert validate_memory(snapshot,{'prose1':'Тут нова студія.'})==snapshot
    with pytest.raises(ValueError): validate_memory(snapshot,{'prose1':'Інша подія'})
    with pytest.raises(ValueError): validate_memory(snapshot,{'other':'нова студія'})
