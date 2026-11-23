"""DATA-010-S02: the story menu accepts all waiting prose as the author's in one transaction."""
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.repository import Repository
from tests.link_helpers import approve_links


def hand_brief(repo,scene_id):
    # VALID-LINKS: prose waits when its brief→prose link is invalid; prose with no brief (link missing) is never listed,
    # so every waiting scene gets a hand-made brief under its manual prose.
    scene=repo.get_scene(scene_id)
    brief=repo.save_version(scene.story_id,scene.id,'brief',f'Завдання: {scene.title}',[])
    return repo.set_head(scene.id,'brief',brief.id,scene.revision)


def book(tmp_path, count=3, briefs=True):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Перевірка'))
    for n in range(count):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {n+1}',beats=f'План {n+1}'))
        if briefs:
            scene=hand_brief(repo,scene.id)
        save_manual_prose(repo,scene.id,f'Проза {n+1}.',scene.revision)
    return repo,story


def swap(repo,story):
    # A move changes the order every text records, so all prose waits for review.
    ids=[s.id for s in repo.list_scenes(story.id)]
    repo.reorder_scenes(story.id,[ids[1],ids[0],*ids[2:]],repo.get_story(story.id).revision)


def waiting(repo,story):
    """Stale prose heads (also when the scene needs review), in reading order."""
    # VALID-LINKS: the hand-made briefs stay unchecked (bulk acceptance confirms prose only), so only prose is counted
    view=repo.context_view(story.id);out=[]
    for scene in view.list_scenes(story.id):
        for material in ('prose',):
            id=scene.heads.get(material)
            if id and (view.is_stale(id) or (material=='prose' and view.effective_scene(scene.id).needs_review)):out.append(material)
    return out


def accept_all(repo,story):
    preview=repo.preview_prose_acceptance(story.id)
    return preview,repo.accept_all_prose(story.id,preview['fingerprint'])


@pytest.mark.req('DATA-010')
def test_all_waiting_prose_is_accepted_and_consecutive_scenes_stay_current(tmp_path):
    repo,story=book(tmp_path)
    swap(repo,story)
    assert waiting(repo,story)==['prose','prose','prose']
    texts={s.id:repo.read_text(s.heads['prose']) for s in repo.list_scenes(story.id)}
    preview,result=accept_all(repo,story)
    assert [s['title'] for s in preview['scenes']]==['Сцена 2','Сцена 1','Сцена 3']
    assert [a['title'] for a in result['accepted']]==['Сцена 2','Сцена 1','Сцена 3']
    # The author baseline of scene 2 and 3 holds the acceptance of the scenes before: nothing is stale afterwards.
    assert waiting(repo,story)==[]
    for scene in repo.list_scenes(story.id):
        assert not repo.get_version(scene.heads['prose']).stale and not scene.needs_review
        assert repo.read_text(scene.heads['prose'])==texts[scene.id]
    records=repo.list_acceptances(story.id)
    assert len(records)==3 and {r.action for r in records}=={'accept_prose'}
    assert repo.preview_prose_acceptance(story.id)['scenes']==[]


@pytest.mark.req('DATA-010')
def test_only_prose_is_accepted_and_fresh_prose_gets_no_record(tmp_path):
    repo,story=book(tmp_path,2)
    first,second=repo.list_scenes(story.id)
    brief=repo.save_version(story.id,first.id,'brief','{}',[first.heads['prose']])
    memory=repo.save_version(story.id,first.id,'memory','{}',[first.heads['prose']])
    save_manual_prose(repo,first.id,'Нова проза 1.',repo.get_scene(first.id).revision)
    # VALID-LINKS: fresh prose is prose whose brief→prose link holds; the author confirms scene 1's links
    approve_links(repo,story.id,{first.id})
    assert repo.get_version(brief.id).stale and repo.get_version(memory.id).stale
    waiting_ids=[s['scene_id'] for s in repo.preview_prose_acceptance(story.id)['scenes']]
    assert waiting_ids==[second.id]
    accept_all(repo,story)
    assert repo.get_version(brief.id).stale and repo.get_version(memory.id).stale
    assert [r.scene_id for r in repo.list_acceptances(story.id)]==[second.id]


@pytest.mark.req('DATA-010')
def test_change_after_preview_rejects_everything(tmp_path):
    repo,story=book(tmp_path,2)
    swap(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    second=repo.list_scenes(story.id)[1]
    save_manual_prose(repo,second.id,'Інша проза.',second.revision)
    heads={s.id:s.heads['prose'] for s in repo.list_scenes(story.id)}
    with pytest.raises(RevisionConflict):
        repo.accept_all_prose(story.id,preview['fingerprint'])
    assert repo.list_acceptances(story.id)==[]
    assert {s.id:s.heads['prose'] for s in repo.list_scenes(story.id)}==heads
    assert repo.get_scene(repo.list_scenes(story.id)[0].id).needs_review


@pytest.mark.req('DATA-010')
def test_saved_impact_run_does_not_block_bulk_acceptance(tmp_path):
    """R-28 is removed (R-44 PR 1): an impact run left open in an old database is history and blocks nothing."""
    from storygen.run_models import Run, RunRequest
    repo,story=book(tmp_path,2)
    swap(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    assert len(preview['scenes'])==2
    repo.enqueue_run(Run(id='review',story_id=story.id,request_id='review',request=RunRequest(story_id=story.id,mode='impact'),state='needs_review',tasks=[]))
    assert len(repo.accept_all_prose(story.id,preview['fingerprint'])['accepted'])==2


@pytest.mark.req('DATA-010')
def test_nothing_waiting_gives_an_empty_preview(tmp_path):
    # VALID-LINKS: prose without a brief has no brief→prose link to check and is not listed
    repo,story=book(tmp_path,2,briefs=False)
    preview,result=accept_all(repo,story)
    assert preview['scenes']==[] and result['accepted']==[]


@pytest.mark.req('DATA-010')
def test_http_preview_accept_and_stale_fingerprint(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.web.app import create_app
    from storygen.application.settings import AppSettings
    app=create_app(AppSettings(data_dir=tmp_path))
    repo=app.state.repo
    story=repo.create_story(StoryCreate(title='HTTP'))
    for n in range(2):
        scene=hand_brief(repo,repo.create_scene(story.id,SceneCreate(title=f'S{n}')).id)
        save_manual_prose(repo,scene.id,f'P{n}.',scene.revision)
    swap(repo,story)
    client=TestClient(app,base_url='http://127.0.0.1:8765')
    url=f'/api/stories/{story.id}/prose-acceptance'
    data=client.get(url).json()
    assert [s['title'] for s in data['scenes']]==['S1','S0']
    accepted=client.post(url,json={'fingerprint':data['fingerprint']})
    assert accepted.status_code==200 and len(accepted.json()['accepted'])==2
    assert client.get(url).json()['scenes']==[]
    assert client.post(url,json={'fingerprint':data['fingerprint']}).status_code==409


# Defect of 22.11.2026 (book V-K): the list was fixed before the first acceptance, but a scene's author baseline
# records the acceptance ID of the earlier prose, so accepting one scene made current later scenes wait
# (`source_baseline_changed`). One click must now leave nothing waiting.
def rename(repo,scene_id):
    scene=repo.get_scene(scene_id)
    repo.update_scene_metadata(scene.id,{'title':scene.title+' *'},scene.revision)


def snapshot(repo,story):
    return {s.id:(s.heads.get('prose'),s.revision,s.needs_review,repo.read_text(s.heads['prose'])) for s in repo.list_scenes(story.id)}


def accept_once_and_check(repo,story):
    texts={s.id:repo.read_text(s.heads['prose']) for s in repo.list_scenes(story.id)}
    before=len(repo.list_acceptances(story.id))
    preview,result=accept_all(repo,story)
    # The listed scenes are accepted in reading order; the later scenes their acceptance makes wait come with them.
    ids=[a['scene_id'] for a in result['accepted']]
    listed=[s['scene_id'] for s in preview['scenes']]
    assert [id for id in ids if id in listed]==listed
    assert waiting(repo,story)==[]
    assert repo.preview_prose_acceptance(story.id)['scenes']==[]
    view=repo.context_view(story.id)
    for scene in repo.list_scenes(story.id):
        assert not view.is_stale(scene.heads['prose']) and not view.effective_scene(scene.id).needs_review
        assert repo.read_text(scene.heads['prose'])==texts[scene.id]
    assert len(repo.list_acceptances(story.id))-before==len(result['accepted'])
    return [a['title'] for a in result['accepted']]


@pytest.mark.req('DATA-010')
def test_one_click_also_accepts_later_scenes_the_acceptance_makes_wait(tmp_path):
    repo,story=book(tmp_path,5)
    first,second,*_=repo.list_scenes(story.id)
    # VALID-LINKS: an acceptance changes no later link, so later scenes wait from the start (their links are invalid)
    # rather than after the acceptance; scene 1's links are confirmed, so it stays unlisted
    approve_links(repo,story.id,{first.id})
    rename(repo,second.id)
    assert [s['title'] for s in repo.preview_prose_acceptance(story.id)['scenes']]==['Сцена 2 *','Сцена 3','Сцена 4','Сцена 5']
    assert accept_once_and_check(repo,story)==['Сцена 2 *','Сцена 3','Сцена 4','Сцена 5']
    assert first.id not in {r.scene_id for r in repo.list_acceptances(story.id)}


@pytest.mark.req('DATA-010')
def test_model_prose_with_dependency_edges_stays_accepted(tmp_path):
    repo,story=book(tmp_path,1)
    first=repo.list_scenes(story.id)[0]
    previous=first.heads['prose']
    stale_kept=[]
    for n in (2,3,4):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {n}',beats=f'План {n}'))
        prose=repo.save_version(story.id,scene.id,'edited',f'Модельна проза {n}.',[previous])
        scene=repo.get_scene(scene.id);scene.heads['prose']=prose.id
        with repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE');repo._save_scene(db,scene)
        stale_kept.append(repo.save_version(story.id,scene.id,'memory','{}',[prose.id]).id)
        previous=prose.id
    rename(repo,first.id)
    accept_once_and_check(repo,story)
    # Accepting prose confirms no memory: the memory the new decisions invalidated stays stale.
    assert all(repo.get_version(id).stale for id in stale_kept)


def arced_book(tmp_path,arcs,parts):
    from storygen.domain import Arc, BookStructure, Part
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Арки'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {n+1}',beats=f'План {n+1}')) for n in range(len(arcs))]
    structure=BookStructure(parts=[Part(id=f'p{i}',arcs=[Arc(id=a) for a in part]) for i,part in enumerate(parts,1)])
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current=repo._active_story(db,story.id)
        repo._save_story(db,current.model_copy(update={'book_structure':structure,'scene_arcs':dict(zip([s.id for s in scenes],arcs))}))
    for n,scene in enumerate(scenes):
        scene=hand_brief(repo,scene.id)
        save_manual_prose(repo,scene.id,f'Проза {n+1}.',scene.revision)
    return repo,repo.get_story(story.id)


@pytest.mark.req('DATA-010')
@pytest.mark.parametrize('arcs,parts',[('AABB',[['A'],['B']]),('ABAB',[['A','B']]),('AABBA',[['A','B']])])
@pytest.mark.parametrize('reorder',[False,True])
def test_parts_arcs_and_a_changed_order_leave_nothing_waiting(tmp_path,arcs,parts,reorder):
    repo,story=arced_book(tmp_path,arcs,parts)
    if reorder:
        swap(repo,story)
    rename(repo,repo.list_scenes(story.id)[0].id)
    assert accept_once_and_check(repo,story)


@pytest.mark.req('DATA-010')
def test_second_pass_after_an_upstream_change_accepts_everything_again(tmp_path):
    repo,story=book(tmp_path,4)
    swap(repo,story)
    assert len(accept_once_and_check(repo,story))==4
    # VALID-LINKS: accepted prose never waits again after an upstream change; only new prose makes a scene wait
    second=repo.list_scenes(story.id)[1]
    save_manual_prose(repo,second.id,'Нова проза.',second.revision)
    assert accept_once_and_check(repo,story)==['Сцена 1']


@pytest.mark.req('DATA-010')
def test_preview_writes_nothing_and_an_unlisted_scene_changed_after_it_rejects_everything(tmp_path):
    repo,story=book(tmp_path,4)
    # VALID-LINKS: scene 1's links are confirmed, so scenes 2–4 (invalid links) are listed and scene 1 is not
    approve_links(repo,story.id,{repo.list_scenes(story.id)[0].id})
    rename(repo,repo.list_scenes(story.id)[1].id)
    before=snapshot(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    assert [s['title'] for s in preview['scenes']]==['Сцена 2 *','Сцена 3','Сцена 4']
    assert snapshot(repo,story)==before and repo.list_acceptances(story.id)==[]
    # Scene 1 is not listed: its change after the preview is a conflict too.
    first=repo.list_scenes(story.id)[0]
    save_manual_prose(repo,first.id,'Інша проза 1.',first.revision)
    before=snapshot(repo,story)
    with pytest.raises(RevisionConflict):
        repo.accept_all_prose(story.id,preview['fingerprint'])
    assert snapshot(repo,story)==before and repo.list_acceptances(story.id)==[]


@pytest.mark.req('DATA-010')
def test_scene_still_waiting_after_its_own_acceptance_stops_without_changes(tmp_path,monkeypatch):
    from storygen.storage import acceptance
    repo,story=book(tmp_path,3)
    rename(repo,repo.list_scenes(story.id)[0].id)
    first=repo.list_scenes(story.id)[0]
    real=acceptance._waiting_prose
    # A reason the author decision does not clear (e.g. a changed review authority) keeps scene 1 waiting.
    monkeypatch.setattr(acceptance,'_waiting_prose',lambda view:[(view.get_scene(first.id),first.heads['prose'])]+[r for r in real(view) if r[0].id!=first.id])
    before=snapshot(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    with pytest.raises(ValueError,match='Сцена 1'):
        repo.accept_all_prose(story.id,preview['fingerprint'])
    assert snapshot(repo,story)==before and repo.list_acceptances(story.id)==[]
