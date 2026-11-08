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


def _save_scene(repo,scene,prose,new_events):
    """Save manual prose and append journal events (dicts without event_id/source) for this scene."""
    from storygen.generation.dependencies import save_manual_prose
    from storygen.memory.journal import load_memory
    from storygen.memory.service import save_scene_memory
    save_manual_prose(repo,scene.id,prose,scene.revision)
    scene=repo.get_scene(scene.id);prose_id=scene.heads['prose']
    earlier=[s for s in repo.list_scenes(scene.story_id) if s.position<scene.position]
    previous=load_memory(repo.read_text(earlier[-1].heads['memory'])) if earlier else MemoryJournal()
    events=[e.model_dump() for e in previous.events]
    for i,item in enumerate(new_events):
        events.append({'character_ids':[],**item,'event_id':f'{prose_id}-{i}','source_version_id':prose_id})
    raw=json_dumps(dict(schema_version=2,source_prose_ids=previous.source_prose_ids+[prose_id],events=events))
    save_scene_memory(repo,scene.id,raw,scene.revision)
    return repo.get_scene(scene.id)


def json_dumps(value):
    import json
    return json.dumps(value,ensure_ascii=False)


def claim_by_text(repo,scene,text):
    from storygen.memory.journal import load_memory
    journal=load_memory(repo.read_text(repo.get_scene(scene.id).heads['memory']))
    return next(e.claim_id for e in journal.events if e.text==text)


@pytest.fixture
def synthetic_repo(tmp_path):
    """4 scenes, cards for Марія and Остап. Returns (repo, story_id, info) with claim IDs and character IDs."""
    from storygen.authoring.imports import SourceFile, import_sources
    from storygen.characters.models import load_characters
    from storygen.domain import SceneCreate, StoryCreate
    from storygen.storage.repository import Repository
    repo=Repository(tmp_path/'data');story=repo.create_story(StoryCreate(title='Синтетика'))
    import_sources(repo,story.id,[SourceFile(name='c.md',raw='## Марія\nГероїня\n## Остап\nСусід'.encode(),kind='source_characters')])
    cards=load_characters(repo.read_text(repo.get_story(story.id).characters_version_id))
    ids={c.name:c.id for c in cards};m,o=ids['Марія'],ids['Остап']
    casts=[[m],[m,o],[m],[o]]
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {i+1}',beats=f'План {i+1}',character_ids=cast)) for i,cast in enumerate(casts)]
    info={'maria':m,'ostap':o}
    s=_save_scene(repo,scenes[0],'Бачили Марію біля моря. Марія вдягла халат. Хтось украв ключ.',[
        dict(claim_id='a',operation='add',category='facts',text='Марію бачили біля моря',quote='Бачили Марію біля моря.'),
        dict(claim_id='b',operation='add',category='character_states',text='Марія в халаті',quote='Марія вдягла халат.',character_ids=[m]),
        dict(claim_id='c',operation='add',category='open_threads',text='Хто вкрав ключ',quote='Хтось украв ключ.')])
    info.update(fact=claim_by_text(repo,s,'Марію бачили біля моря'),state=claim_by_text(repo,s,'Марія в халаті'),thread=claim_by_text(repo,s,'Хто вкрав ключ'))
    s=_save_scene(repo,scenes[1],'Остап приніс хліб. Пішов дощ.',[
        dict(claim_id='d',operation='add',category='character_states',text='Іде дощ',quote='Пішов дощ.'),
        dict(claim_id='e',operation='add',category='timeline',text='Остап приніс хліб',quote='Остап приніс хліб.')])
    info['hidden']=claim_by_text(repo,s,'Іде дощ')
    from storygen.memory.forwarding import memory_view, save_forwarding
    view=memory_view(repo,s.id);save_forwarding(repo,s.id,{info['hidden']:False},view['expected_revision'],view['fingerprint'])
    s=_save_scene(repo,repo.get_scene(scenes[2].id),'Марія зняла халат.',[
        dict(claim_id=info['state'],operation='update',category='character_states',text='Марія без халата',quote='Марія зняла халат.',character_ids=[m])])
    s=_save_scene(repo,repo.get_scene(scenes[3].id),'Ключ знайшовся.',[
        dict(claim_id=info['thread'],operation='retire',category='open_threads',text='Ключ знайшовся',quote='Ключ знайшовся.')])
    return repo,story.id,info
