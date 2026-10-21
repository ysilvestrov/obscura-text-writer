import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.generation.context import build_context
from storygen.providers.models import RoleSettings, ProviderSettings


def chain(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Префікс'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {i+1}',beats='Черговий епізод')) for i in range(7)]
    ids=[];facts=[]
    for i,scene in enumerate(scenes):
        text=f'Доказова проза номер {i}, яка вже відбулася. ПІЗНІЙ_СЕКРЕТ_{i}'
        prose=repo.save_version(story.id,scene.id,'manual',text,[])
        repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
        ids.append(prose.id);facts.append(MemoryEntry(text=f'Відомий факт {i}',source_version_id=prose.id,quote=text))
        memory=repo.save_version(story.id,scene.id,'memory',MemorySnapshot(facts=facts.copy(),source_prose_ids=ids.copy()).model_dump_json(),ids.copy())
        repo.set_head(scene.id,'memory',memory.id,repo.get_scene(scene.id).revision)
    return repo,scenes,ids


def test_earlier_scene_uses_only_previous_prefix_after_whole_story_completed(tmp_path):
    from storygen.memory.service import journal_before
    repo,scenes,ids=chain(tmp_path)
    memory=journal_before(repo,scenes[1].id)
    assert memory.source_prose_ids==ids[:1]
    context=build_context(repo,scenes[1].id,'brief',RoleSettings(provider=ProviderSettings(model='fake')))
    section=context.user_text.split('ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n')[1].split('\n\nЗАВЕРШЕННЯ')[0]
    assert 'Відомий факт 0' in section and 'Відомий факт 1' not in section
    assert 'quote' not in section and ids[0] not in section
    assert 'ПІЗНІЙ_СЕКРЕТ_5' not in context.user_text
    assert context.memory_metrics['event_count']==1
    assert ids[0] in context.input_refs and ids[5] not in context.input_refs


def test_exact_future_source_quote_cannot_be_memory_of_earlier_scene(tmp_path):
    from storygen.memory.service import journal_before
    repo,scenes,ids=chain(tmp_path)
    memory=MemorySnapshot(facts=[MemoryEntry(text='Майбутнє',source_version_id=ids[5],quote=repo.read_text(ids[5]))],source_prose_ids=[ids[5]])
    ref=repo.save_version(scenes[0].story_id,scenes[0].id,'memory',memory.model_dump_json(),[ids[5]])
    repo.set_head(scenes[0].id,'memory',ref.id,repo.get_scene(scenes[0].id).revision)
    with pytest.raises(ValueError,match='пам’ять'):
        journal_before(repo,scenes[1].id)
