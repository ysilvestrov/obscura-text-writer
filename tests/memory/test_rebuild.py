import json
import threading
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.memory.service import rebuild_memory


def test_rebuild_memory_uses_current_texts_in_order(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(3)]
    sources=[]
    for scene in scenes:
        prose=save_manual_prose(repo,scene.id,f'Сцена {scene.position}',0);sources.append(prose.id)
    first=MemorySnapshot(facts=[MemoryEntry(text='Початок',source_version_id=sources[0],quote='Сцена 0')],source_prose_ids=[sources[0]])
    mem=repo.save_version(story.id,scenes[0].id,'memory',first.model_dump_json(),[sources[0]]);repo.set_head(scenes[0].id,'memory',mem.id,1)
    calls=[]
    class Gateway:
        def stream(self,context,cancel):
            calls.append(context.scene_id)
            current=repo.get_scene(context.scene_id)
            snapshot=MemorySnapshot(facts=first.facts,source_prose_ids=sources[:current.position+1])
            yield GenerationEvent(type='delta',text=snapshot.model_dump_json())
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempts=rebuild_memory(repo,scenes[1].id,lambda _:Gateway(),threading.Event(),lambda *_:None,settings=RoleSettings(provider=ProviderSettings(model='test')))
    assert calls==[s.id for s in scenes[1:]] and all(a.state=='completed' for a in attempts)
    snapshot=MemorySnapshot.model_validate_json(repo.read_text(repo.get_scene(scenes[-1].id).heads['memory']))
    assert snapshot.source_prose_ids==sources
