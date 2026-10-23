import json
import threading

import pytest

from storygen.domain import RevisionConflict, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository

TEXT = 'Це не ваші провина. Вона торкалається скла. '+'Спокійний ранок тривав. '*8
PROPOSAL = {'edits': [
    {'fragment_id': 'f000001', 'original': 'ваші', 'replacement': 'ваша', 'category': 'grammar'},
    {'fragment_id': 'f000001', 'original': 'торкалається', 'replacement': 'торкається', 'category': 'spelling'},
]}


def generate(tmp_path, mode='review', proposal=None, run_id=None):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Редактура'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок'))
    draft = repo.save_version(story.id, scene.id, 'draft', TEXT, [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    settings = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', edit_review=mode)
    if run_id:
        from storygen.run_models import Run, RunRequest
        repo.enqueue_run(Run(id=run_id,story_id=story.id,request_id=run_id,
            request=RunRequest(story_id=story.id,scene_id=scene.id,mode='scene'),state='running',
            tasks=[{'scene_id':scene.id,'stage':'edit'},{'scene_id':scene.id,'stage':'memory'}]))
    context = build_context(repo, scene.id, 'edit', settings)
    raw = json.dumps(PROPOSAL if proposal is None else proposal, ensure_ascii=False)
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, 'edit', context, Gateway(), threading.Event(), lambda _: None, run_id,0 if run_id else None)
    return repo, scene, draft, attempt


def choose(repo, scene, attempt, indices):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    preview = copyedit_preview(repo, scene.id, attempt.id)
    return select_copyedits(repo, scene.id, attempt.id, indices, preview['expected_revision'], preview['proposal_fingerprint'])


def test_review_pauses_without_publish_and_subset_preserves_original(tmp_path):
    repo, scene, draft, attempt = generate(tmp_path)
    assert attempt.state == 'needs_review' and attempt.result_version_id is None
    assert not repo.get_scene(scene.id).heads.get('prose')
    result = choose(repo, scene, attempt, [1])
    assert repo.read_text(result['version'].id) == TEXT.replace('торкалається', 'торкається')
    assert repo.read_text(draft.id) == TEXT
    stored = repo.get_attempt(attempt.id)
    assert stored.state == 'completed' and stored.result_version_id == result['version'].id
    assert stored.context['copyedit_decisions'][-1]['selected_indices'] == [1]


def test_auto_records_all_and_author_can_revise_to_empty_selection(tmp_path):
    repo, scene, draft, attempt = generate(tmp_path, 'auto')
    assert attempt.state == 'completed'
    assert attempt.context['copyedit_decisions'][0]['selected_indices'] == [0, 1]
    assert repo.read_text(attempt.result_version_id) == TEXT.replace('ваші', 'ваша').replace('торкалається', 'торкається')
    result = choose(repo, scene, attempt, [])
    assert repo.read_text(result['version'].id) == TEXT
    assert len(repo.get_attempt(attempt.id).context['copyedit_decisions']) == 2
    assert any(w['quote']=='ваші провина' for w in repo.get_attempt(attempt.id).context['copyedit_decisions'][-1]['language_warnings'])


@pytest.mark.parametrize('indices', [[-1], [2], [0, 0], [True], ['0']])
def test_bad_indices_never_publish(tmp_path, indices):
    repo, scene, _, attempt = generate(tmp_path)
    with pytest.raises(ValueError):
        choose(repo, scene, attempt, indices)
    assert not repo.get_scene(scene.id).heads.get('prose')


@pytest.mark.parametrize('change', ['draft', 'prose', 'prose_back', 'revision', 'fingerprint', 'foreign'])
def test_changed_inputs_or_targets_cannot_publish(tmp_path, change):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    repo, scene, _, attempt = generate(tmp_path)
    preview = copyedit_preview(repo, scene.id, attempt.id)
    target_scene = scene.id
    if change in {'draft', 'prose', 'prose_back'}:
        head = 'draft' if change == 'draft' else 'prose'
        kind = 'draft' if change == 'draft' else 'manual'
        ref = repo.save_version(scene.story_id, scene.id, kind, 'Інший текст.', [])
        repo.set_head(scene.id, head, ref.id, repo.get_scene(scene.id).revision)
        if change == 'prose_back':
            # Even an equivalent empty prose slot cannot erase the head revision.
            with repo.db.connection() as db:
                current = repo.get_scene(scene.id)
                current.heads.pop('prose')
                repo._save_scene(db, current)
    elif change == 'revision':
        repo.update_scene_metadata(scene.id, {'target_words': 1200}, repo.get_scene(scene.id).revision)
    elif change == 'fingerprint':
        preview['proposal_fingerprint'] = 'forged'
    elif change == 'foreign':
        story = repo.create_story(StoryCreate(title='Інший'))
        target_scene = repo.create_scene(story.id, SceneCreate(title='Інша')).id
    revision = preview['expected_revision'] if change == 'revision' else repo.get_scene(scene.id).revision
    with pytest.raises((ValueError, RevisionConflict)):
        select_copyedits(repo, target_scene, attempt.id, [0], revision, preview['proposal_fingerprint'])
    assert not repo.get_attempt(attempt.id).context.get('copyedit_decisions')


@pytest.mark.parametrize('mode',['review','auto'])
@pytest.mark.parametrize('edits',[[],[dict(fragment_id='f000001',original='ваші',replacement='ваші',category='grammar')]])
def test_no_changes_cannot_be_accepted_or_auto_published(tmp_path,mode,edits):
    repo, scene, _, attempt = generate(tmp_path,mode,proposal={'edits':edits})
    assert attempt.state == 'failed'
    assert attempt.context['editor_failure']['category']=='no_changes'
    assert 'Редактор не запропонував змін' in attempt.error
    assert not attempt.result_version_id and not repo.get_scene(scene.id).heads.get('prose')
    assert not any(v.kind=='edited' for v in repo.list_versions(scene.story_id,scene.id))


def test_historical_empty_proposal_is_readable_but_cannot_publish(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview,select_copyedits
    repo,scene,draft,attempt=generate(tmp_path)
    attempt.context['copyedit_proposal']['proposal']['edits']=[]
    repo.save_attempt(attempt)
    preview=copyedit_preview(repo,scene.id,attempt.id)
    assert not preview['can_apply'] and 'не запропонував змін' in preview['reason']
    with pytest.raises(ValueError,match='не запропонував змін'):
        select_copyedits(repo,scene.id,attempt.id,[],preview['expected_revision'],preview['proposal_fingerprint'])
    ref=repo.save_version(scene.story_id,scene.id,'edited',TEXT,attempt.context['input_refs'],dependency_snapshot=attempt.context['dependency_snapshot'])
    with pytest.raises(ValueError,match='не запропонував змін'):
        repo.commit_copyedit_selection(attempt.id,ref,[],preview['expected_revision'],preview['proposal_fingerprint'],[])
    assert not repo.get_scene(scene.id).heads.get('prose')
    assert not repo.get_attempt(attempt.id).context.get('copyedit_decisions')


def test_invalid_whole_proposal_cannot_be_salvaged_by_subset(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview
    proposal = {'edits': PROPOSAL['edits'] + [dict(fragment_id='f000001', original='не', replacement='', category='grammar')]}
    repo, scene, _, attempt = generate(tmp_path, proposal=proposal)
    assert attempt.state == 'failed'
    with pytest.raises(ValueError):
        copyedit_preview(repo, scene.id, attempt.id)


def test_review_run_waits_for_selection_and_continues_without_editor_repeat(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import Run, RunRequest
    repo, scene, _, attempt = generate(tmp_path,run_id='review-run')
    settings=RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches',edit_review='review')
    for role in ['editor','memory']:
        save_role_settings(repo,scene.story_id,role,settings,repo.get_story(scene.story_id).revision)
    run=repo.get_run('review-run');run.state='needs_review';repo.save_run(run)
    worker=RunCoordinator(repo)
    with pytest.raises(ValueError,match='прав'):
        worker.resume(run.id)
    result=choose(repo,scene,attempt,[0])
    resumed=worker.continue_after_acceptance(run.id,result['version'].id,0,result['scene'].revision)
    assert resumed.cursor==1 and resumed.state=='queued'
    assert len(repo.list_attempts(scene.story_id))==1


def test_selection_rechecks_target_inside_storage_transaction(tmp_path,monkeypatch):
    repo, scene, _, attempt = generate(tmp_path)
    real_save=repo.save_version
    def concurrent_save(*args,**kwargs):
        ref=real_save(*args,**kwargs)
        other=real_save(scene.story_id,scene.id,'manual','Конкурентна проза.',[])
        repo.set_head(scene.id,'prose',other.id,repo.get_scene(scene.id).revision)
        return ref
    monkeypatch.setattr(repo,'save_version',concurrent_save)
    with pytest.raises((RevisionConflict,ValueError)):
        choose(repo,scene,attempt,[0])
    assert repo.read_text(repo.get_scene(scene.id).heads['prose'])=='Конкурентна проза.'
    assert not repo.get_attempt(attempt.id).context.get('copyedit_decisions')


def test_cancelled_review_requires_explicit_repeat_authorization(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator
    repo,scene,_,attempt=generate(tmp_path,run_id='cancel-review')
    settings=RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches',edit_review='review')
    for role in ['editor','memory']:
        save_role_settings(repo,scene.story_id,role,settings,repo.get_story(scene.story_id).revision)
    run=repo.get_run('cancel-review');run.state='needs_review';repo.save_run(run)
    worker=RunCoordinator(repo)
    with pytest.raises(ValueError,match='прав'):
        worker.resume(run.id,repeat_interrupted=True)
    assert worker.cancel(run.id).state=='cancelled'
    with pytest.raises(ValueError,match='повтор'):
        worker.resume(run.id,repeat_interrupted=False)
    assert worker.get_run(run.id).state=='cancelled'
    repeated=worker.resume(run.id,repeat_interrupted=True)
    assert repeated.state=='queued' and repeated.cursor==0
    assert len(repo.list_attempts(scene.story_id))==1
