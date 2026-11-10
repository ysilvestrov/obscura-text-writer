"""MEMORY-SELECT-S08: author memory-kind marks act only under selection and stale only versions built with it (#60)."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import RevisionConflict
from storygen.generation.context import SELECTED_PROJECTION, build_context
from storygen.storage.snapshots import compare_snapshot
from storygen.web.app import create_app
from tests.generation.test_context_selection import memory_section, settings, story_with_memory


def claim(journal,text):
    return next(e.claim_id for e in journal.events if e.text==text)


COAST='Подія на узбережжі номер 3: довгий опис того, що сталося біля води'


def tight(repo,scene):
    full=build_context(repo,scene.id,'brief',settings())
    return settings(max_input_chars=len(full.system_text)+len(full.user_text)-400)


def mark(repo,story_id,claim_id,kind):
    return repo.update_memory_kind(story_id,claim_id,kind,repo.get_story(story_id).revision)


def test_core_mark_shows_an_unmatched_entry_under_selection(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    limit=tight(repo,scene)
    before=build_context(repo,scene.id,'brief',limit)
    assert COAST not in memory_section(before)
    mark(repo,scene.story_id,claim(journal,COAST),'core')
    after=build_context(repo,scene.id,'brief',limit)
    assert after.memory_metrics['projection_version']==SELECTED_PROJECTION and COAST in memory_section(after)


def test_atmosphere_mark_moves_an_entry_out_of_its_layer():
    from storygen.memory.selection import classify
    from tests.memory.test_selection import inp
    layers=classify(inp(kinds={'t_ola':'atmosphere'}))
    assert 't_ola' in [i.claim_id for i in layers['atmosphere']] and 't_ola' not in [i.claim_id for i in layers['threads']]


def test_marks_do_not_change_a_fitting_request(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    before=build_context(repo,scene.id,'brief',settings())
    mark(repo,scene.story_id,claim(journal,COAST),'atmosphere')
    after=build_context(repo,scene.id,'brief',settings())
    assert after.fingerprint==before.fingerprint and after.user_text==before.user_text
    assert not any(s.field=='memory_kind_overrides' for s in after.dependency_snapshot.selectors)


def test_mark_stales_only_versions_built_with_selection(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    fitting=build_context(repo,scene.id,'brief',settings()).dependency_snapshot
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    recorded=[s for s in selected.selectors if s.field=='memory_kind_overrides']
    assert len(recorded)==1 and recorded[0].expected=={} and recorded[0].owner_id==scene.id
    mark(repo,scene.story_id,claim(journal,COAST),'core')
    view=repo.context_view(scene.story_id)
    changed=[c for c in compare_snapshot(view,selected) if c.selector and c.selector.field=='memory_kind_overrides']
    assert len(changed)==1 and changed[0].current=={claim(journal,COAST):'core'}
    assert not any(c.selector and c.selector.field=='memory_kind_overrides' for c in compare_snapshot(view,fitting))


def test_mark_of_an_entry_absent_before_the_scene_does_not_stale(tmp_path):
    from storygen.memory.kinds import kind_overrides
    repo,scene,journal,_=story_with_memory(tmp_path)
    first=repo.list_scenes(scene.story_id)[0]
    mark(repo,scene.story_id,claim(journal,COAST),'core')
    # The first scene has no memory before it: its value ignores the mark.
    assert kind_overrides(repo.context_view(scene.story_id),first.id)=={}
    assert kind_overrides(repo.context_view(scene.story_id),scene.id)=={claim(journal,COAST):'core'}


def test_update_memory_kind_cas_validation_and_reset(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    story=repo.get_story(scene.story_id);target=claim(journal,COAST)
    marked=repo.update_memory_kind(story.id,target,'core',story.revision)
    assert marked.memory_kind_overrides=={target:'core'} and marked.revision==story.revision+1
    assert repo.update_memory_kind(story.id,target,'core',marked.revision).revision==marked.revision  # no-op keeps the revision
    with pytest.raises(RevisionConflict):repo.update_memory_kind(story.id,target,'atmosphere',story.revision)
    with pytest.raises(ValueError,match='Запису немає'):repo.update_memory_kind(story.id,'missing','core',marked.revision)
    with pytest.raises(ValueError,match='Слот ядра'):repo.update_memory_kind(story.id,claim(journal,'Синій халат'),'atmosphere',marked.revision)
    cleared=repo.update_memory_kind(story.id,target,None,marked.revision)
    assert cleared.memory_kind_overrides=={} and repo.get_story(story.id).memory_kind_overrides=={}


def test_memory_kind_http(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    story=repo.get_story(scene.story_id);target=claim(journal,COAST)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        url=f'/api/stories/{story.id}/memory-kind'
        response=client.put(url,json={'claim_id':target,'kind':'atmosphere','expected_revision':story.revision})
        assert response.status_code==200 and response.json()['memory_kind_overrides']=={target:'atmosphere'}
        assert client.put(url,json={'claim_id':target,'kind':'core','expected_revision':story.revision}).status_code==409
        revision=response.json()['revision']
        assert client.put(url,json={'claim_id':'missing','kind':'core','expected_revision':revision}).status_code==400
        assert client.put(url,json={'claim_id':target,'kind':'hidden','expected_revision':revision}).status_code==422
        assert client.put(url,json={'claim_id':target,'kind':None,'expected_revision':revision}).json()['memory_kind_overrides']=={}


def test_memory_view_rows_carry_kind_slot_and_story_revision(tmp_path):
    from storygen.memory.forwarding import memory_view
    repo,scene,journal,_=story_with_memory(tmp_path)
    first=repo.list_scenes(scene.story_id)[0]
    story=mark(repo,scene.story_id,claim(journal,COAST),'atmosphere')
    view=memory_view(repo,first.id)
    rows={r['text']:r for r in view['rows']}
    assert view['story_revision']==story.revision
    assert rows[COAST]['kind']=='atmosphere' and rows[COAST]['slot'] is False
    assert rows['Синій халат']['slot'] is True and rows['Синій халат']['kind'] is None


def test_statistics_summary_of_selection_and_narrowing(tmp_path):
    from storygen.application.statistics import memory_summary
    repo,scene,_,_=story_with_memory(tmp_path)
    metrics=build_context(repo,scene.id,'brief',tight(repo,scene)).memory_metrics
    summary=memory_summary(metrics)['memory_selection']
    assert summary['selected']==len(metrics['selection']['selected_claim_ids'])
    assert summary['total']==summary['selected']+summary['dropped'] and summary['dropped']>0
    assert summary['layers']['core']==1 and all(v>0 for v in summary['dropped_layers'].values())
    assert memory_summary({'narrow':{'hidden':3,'mutable_shown':1,'immutable_shown':0}})=={'memory_narrow':{'hidden':3,'mutable_shown':1,'immutable_shown':0}}
    assert memory_summary(build_context(repo,scene.id,'brief',settings()).memory_metrics)=={}


def test_rewrite_style_reentry_with_selection_records_the_selector(tmp_path):
    # build_rewrite_context re-enters make_context with the base metrics and no memory_selector.
    from storygen.generation.context import make_context
    repo,scene,journal,_=story_with_memory(tmp_path)
    limit=tight(repo,scene)
    base=build_context(repo,scene.id,'brief',limit)
    assert 'selection' in base.memory_metrics
    mark(repo,scene.story_id,claim(journal,COAST),'core')
    view=repo.context_view(scene.story_id)
    ctx=make_context(view,view.story,view.get_scene(scene.id),'brief',limit,[base.user_text],list(base.input_refs),dict(base.fragments),
        memory_metrics=base.memory_metrics,context_warnings=base.context_warnings)
    recorded=[s for s in ctx.dependency_snapshot.selectors if s.field=='memory_kind_overrides']
    assert len(recorded)==1 and recorded[0].expected=={claim(journal,COAST):'core'}


def test_legacy_thread_closure_in_the_timeline_takes_a_mark():
    from types import SimpleNamespace
    from storygen.memory.journal import MemoryJournal, _add_event
    from storygen.memory.kinds import kind_overrides
    from storygen.memory.projection import candidate_claim_ids, memory_items
    thread=_add_event('open_threads','Хто стукав?','p1','q',0)
    retire=thread.model_copy(update={'event_id':'e-retire','operation':'retire','text':'Стукав сусід'})
    journal=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[thread,retire])
    items,_=memory_items(journal,[],{'p1':1})
    assert (thread.claim_id,'timeline') in {(i.claim_id,i.section) for i in items}
    assert thread.claim_id in candidate_claim_ids(journal)
    scenes=[SimpleNamespace(id='s1',story_id='st',position=0,heads={'memory':'m'},trashed_at=None),
            SimpleNamespace(id='s2',story_id='st',position=1,heads={},trashed_at=None)]
    class View:
        def peek_scene(self,id):return next(s for s in scenes if s.id==id)
        def peek_scenes(self,_):return scenes
        def peek_story(self,_):return SimpleNamespace(memory_kind_overrides={thread.claim_id:'core'})
        def peek_version(self,_):return SimpleNamespace(relative_path='m',sha256='x')
        def read_blob(self,*_):return journal.model_dump_json().encode()
    assert kind_overrides(View(),'s2')=={thread.claim_id:'core'}
