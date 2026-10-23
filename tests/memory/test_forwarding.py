import json
import pytest
from storygen.domain import StoryCreate,SceneCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.memory.service import save_scene_memory
from storygen.memory.forwarding import memory_view,save_forwarding,hidden_before
from storygen.memory.journal import load_memory
from storygen.memory.projection import project_memory,memory_catalog


def seeded(root):
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Пам’ять'))
    scenes=[];sources=[];facts=[]
    for i in range(3):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {i+1}'))
        text=f'Побутова деталь номер {i+1}.'
        save_manual_prose(repo,scene.id,text,scene.revision)
        scene=repo.get_scene(scene.id);sources.append(scene.heads['prose'])
        facts.append(dict(text=text,source_version_id=sources[-1],quote=text))
        save_scene_memory(repo,scene.id,json.dumps(dict(source_prose_ids=sources,facts=facts)),scene.revision)
        scenes.append(repo.get_scene(scene.id))
    return repo,story,scenes


def apply(repo,scene,choices):
    view=memory_view(repo,scene.id)
    return save_forwarding(repo,scene.id,choices,view['expected_revision'],view['fingerprint'])


def test_boundary_inherited_fact_hide_enable_and_journal_unchanged(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    view=memory_view(repo,scenes[1].id);claim=view['rows'][0]['claim_id']
    before=repo.read_text(scenes[1].heads['memory'])
    result=apply(repo,scenes[1],{claim:False})
    assert not result['rows'][0]['forward'] and result['can_save']
    assert repo.read_text(scenes[1].heads['memory'])==before
    captured=repo.context_view(story.id)
    assert not hidden_before(captured,scenes[1].id)
    assert claim in hidden_before(captured,scenes[2].id)
    later=memory_view(repo,scenes[2].id)
    assert not later['rows'][0]['forward']
    apply(repo,scenes[2],{claim:True})
    assert memory_view(repo,scenes[2].id)['rows'][0]['forward']
    assert not memory_view(repo,scenes[1].id)['rows'][0]['forward']
    assert not repo.get_version(scenes[2].heads['memory']).stale


def test_projection_hides_all_events_of_claim_but_catalog_keeps_it(tmp_path):
    repo,_,scenes=seeded(tmp_path)
    journal=load_memory(repo.read_text(scenes[1].heads['memory']));claim=journal.events[0].claim_id
    projection=project_memory(journal,[],{},hidden_claim_ids={claim})
    assert journal.events[0].text not in projection.text
    assert journal.events[1].text in projection.text
    assert journal.events[0].text in memory_catalog(journal)
    assert projection.metrics['hidden_claim_count']==1


def test_forwarding_cas_unknown_and_earlier_change_conflicts(tmp_path):
    repo,_,scenes=seeded(tmp_path)
    captured=memory_view(repo,scenes[1].id);claim=captured['rows'][0]['claim_id']
    apply(repo,scenes[0],{claim:False})
    with pytest.raises(RevisionConflict):save_forwarding(repo,scenes[1].id,{claim:True},captured['expected_revision'],captured['fingerprint'])
    current=memory_view(repo,scenes[1].id)
    with pytest.raises(ValueError):save_forwarding(repo,scenes[1].id,{'foreign':False},current['expected_revision'],current['fingerprint'])


def test_context_policy_freshness_and_return_to_exact_selection(tmp_path):
    from storygen.generation.context import build_context
    from storygen.providers.models import RoleSettings,ProviderSettings
    repo,story,scenes=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='fake'),context_tokens=128000,max_input_chars=1000000)
    ctx=build_context(repo,scenes[2].id,'brief',role)
    ref=repo.save_version(story.id,scenes[2].id,'brief','Завдання',ctx.input_refs,dependency_snapshot=ctx.dependency_snapshot)
    legacy=ctx.dependency_snapshot.model_copy(update={'selectors':[s for s in ctx.dependency_snapshot.selectors if s.field!='memory_projection_policy']})
    old=repo.save_version(story.id,scenes[2].id,'brief','Старе завдання',ctx.input_refs,dependency_snapshot=legacy)
    claim=memory_view(repo,scenes[1].id)['rows'][0]['claim_id']
    apply(repo,scenes[1],{claim:False})
    assert repo.get_version(ref.id).stale and repo.get_version(old.id).stale
    # The boundary never makes the scene that owns it stale.
    assert not repo.get_version(scenes[1].heads['prose']).stale
    updated=build_context(repo,scenes[2].id,'brief',role)
    assert 'Побутова деталь номер 1.' not in updated.user_text
    assert 'Побутова деталь номер 2.' in updated.user_text
    assert updated.memory_metrics['hidden_claim_count']==1
    apply(repo,scenes[1],{claim:True})
    assert not repo.get_version(ref.id).stale and not repo.get_version(old.id).stale


def test_updated_state_and_retired_thread_remain_hidden_without_erasing_events():
    from storygen.memory.journal import MemoryJournal,MemoryEvent
    def event(id,claim,category,text,source,operation='add'):
        return MemoryEvent(event_id=id,claim_id=claim,category=category,text=text,
            source_version_id=source,operation=operation,quote='Доказ')
    journal=MemoryJournal(source_prose_ids=['p1','p2'],events=[
        event('e1','state','character_states','Було холодно','p1'),
        event('e2','thread','open_threads','Знайти ключ','p1'),
        event('e3','state','character_states','Стало тепло','p2','update'),
        event('e4','thread','open_threads','Ключ знайдено','p2','retire')])
    raw=journal.model_dump_json()
    projection=project_memory(journal,[],{'p1':1,'p2':2},hidden_claim_ids={'state','thread'})
    assert all(text not in projection.text for text in ['Було холодно','Стало тепло','Знайти ключ','Ключ знайдено'])
    assert 'Стало тепло' in memory_catalog(journal)
    assert journal.model_dump_json()==raw
