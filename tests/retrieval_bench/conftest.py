import sys
from pathlib import Path

import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'
if str(SCRIPTS) not in sys.path:sys.path.insert(0,str(SCRIPTS))

from storygen.memory.journal import MemoryEvent, MemoryJournal  # noqa: E402


def event(n,claim,op,category,text,source,chars=()):
    return MemoryEvent(event_id=f'e{n}',claim_id=claim,operation=op,category=category,text=text,
        character_ids=list(chars),source_version_id=source,quote='q')


@pytest.fixture
def journal_fixture():
    """Facts, scoped and unscoped states (one updated), a thread retired later, timeline."""
    return MemoryJournal(source_prose_ids=['p1','p2'],events=[
        event(1,'f1','add','facts','Марія живе біля моря','p1'),
        event(2,'s1','add','character_states','Марія в халаті','p1',['c1']),
        event(3,'s2','add','character_states','Іде дощ','p1'),
        event(4,'t1','add','open_threads','Хто вкрав ключ','p1'),
        event(5,'h1','add','timeline','Марія прийшла','p1'),
        event(6,'s1','update','character_states','Марія без халата','p2',['c1']),
        event(7,'t1','retire','open_threads','Ключ знайшовся','p2'),
        event(8,'h2','add','timeline','Остап поїхав','p2')])


NUMBERS={'p1':1,'p2':2}
