import pytest
from storygen.domain import StoryCreate, SceneCreate, StageAttempt, new_id
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.context import build_context
from storygen.memory.models import MemorySnapshot


def setup_memory(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=str(i), beats='План')) for i in range(7)]
    p1 = repo.save_version(story.id, scenes[0].id, 'manual', 'Перша проза', [])
    repo.set_head(scenes[0].id, 'prose', p1.id, 0)
    memory = repo.save_version(story.id, scenes[0].id, 'memory', MemorySnapshot(source_prose_ids=[p1.id]).model_dump_json(), [p1.id])
    repo.set_head(scenes[0].id, 'memory', memory.id, 1)
    p2 = repo.save_version(story.id, scenes[1].id, 'manual', 'Друга проза', [])
    repo.set_head(scenes[1].id, 'prose', p2.id, 0)
    role = RoleSettings(provider=ProviderSettings(model='frozen'),memory_mode='snapshot')
    context = build_context(repo, scenes[1].id, 'memory', role)
    return repo, story, scenes, context


def publish(repo, context, legacy=False):
    payload = context.model_dump()
    if legacy:
        payload.pop('dependency_snapshot'); payload.pop('target_cas')
    attempt = StageAttempt(id=new_id(), story_id=context.story_id, scene_id=context.scene_id, stage=context.stage, context=payload, partial_path='partial.txt')
    repo.save_attempt(attempt)
    ref = repo.save_version(context.story_id, context.scene_id, {'edit':'edited','memory':'memory','brief':'brief'}[context.stage], 'Результат', context.input_refs)
    return repo.commit_stage_result(attempt.id, ref, context.scene_revision), ref


def test_scene_six_plan_change_does_not_block_scene_two_memory(tmp_path):
    repo, story, scenes, context = setup_memory(tmp_path)
    repo.update_scene_plan(scenes[5].id, 'Новий план', 0)
    attempt, ref = publish(repo, context)
    assert attempt.state == 'completed'
    assert repo.get_scene(scenes[1].id).heads['memory'] == ref.id


def test_unrelated_role_change_does_not_block_patches(tmp_path):
    repo, story, scenes, _ = setup_memory(tmp_path)
    scene = repo.get_scene(scenes[1].id)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Чернетка', [])
    scene = repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='fixed'), edit_mode='patches'))
    repo.write_role_settings(story.id, {'writer': RoleSettings(provider=ProviderSettings(model='new')).model_dump()}, repo.get_story(story.id).revision)
    attempt, ref = publish(repo, context)
    assert attempt.state == 'completed'
    assert repo.get_scene(scene.id).heads['prose'] == ref.id


@pytest.mark.parametrize('scene_index,head,kind', [(1,'prose','manual'), (0,'memory','memory')])
def test_replaced_prose_or_previous_memory_blocks_publication(tmp_path, scene_index, head, kind):
    repo, story, scenes, context = setup_memory(tmp_path)
    scene = repo.get_scene(scenes[scene_index].id)
    ref = repo.save_version(story.id, scene.id, kind, 'Заміна', [])
    repo.set_head(scene.id, head, ref.id, scene.revision)
    attempt, result = publish(repo, context)
    assert attempt.state == 'alternative'
    assert 'memory' not in repo.get_scene(scenes[1].id).heads
    assert repo.read_text(result.id) == 'Результат'


def test_added_canon_conflicts_with_missing_selector(tmp_path):
    repo, story, scenes, _ = setup_memory(tmp_path)
    context = build_context(repo, scenes[0].id, 'brief', RoleSettings(provider=ProviderSettings(model='fixed')))
    canon = repo.save_version(story.id, None, 'canon', 'Новий', [])
    cards = repo.save_version(story.id, None, 'character_cards', '[]', [])
    repo.publish_blueprint(story.id, canon.id, cards.id, [], repo.get_story(story.id).revision)
    assert publish(repo, context)[0].state == 'alternative'


def test_target_head_aba_still_conflicts(tmp_path):
    repo, story, scenes, _ = setup_memory(tmp_path)
    scene = repo.get_scene(scenes[1].id)
    first = repo.save_version(story.id, scene.id, 'memory', '{}', [])
    scene = repo.set_head(scene.id, 'memory', first.id, scene.revision)
    context = build_context(repo, scene.id, 'memory', RoleSettings(provider=ProviderSettings(model='frozen')))
    second = repo.save_version(story.id, scene.id, 'memory', '{}', [])
    scene = repo.set_head(scene.id, 'memory', second.id, scene.revision)
    scene = repo.set_head(scene.id, 'memory', first.id, scene.revision)
    attempt, _ = publish(repo, context)
    assert attempt.state == 'alternative'
    assert repo.get_scene(scene.id).heads['memory'] == first.id


def test_legacy_attempt_keeps_conservative_revision_check(tmp_path):
    repo, story, scenes, context = setup_memory(tmp_path)
    repo.update_scene_plan(scenes[5].id, 'Інший план', 0)
    assert publish(repo, context, legacy=True)[0].state == 'alternative'


def test_role_change_applies_to_next_stage(tmp_path):
    repo, story, scenes, context = setup_memory(tmp_path)
    new = RoleSettings(provider=ProviderSettings(model='next'))
    repo.write_role_settings(story.id, {'memory': new.model_dump()}, repo.get_story(story.id).revision)
    assert context.settings.provider.model == 'frozen'
    assert publish(repo, context)[0].state == 'completed'
    settings = RoleSettings.model_validate(repo.read_role_settings(story.id)['memory'])
    assert build_context(repo, scenes[1].id, 'memory', settings).settings.provider.model == 'next'


def test_memory_changed_during_call_is_validated_against_captured_prose(tmp_path):
    import threading
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.stages import execute_stage
    repo, story, scenes, context = setup_memory(tmp_path)
    class Gateway:
        def stream(self, context, cancel):
            scene = repo.get_scene(scenes[1].id)
            new = repo.save_version(story.id, scene.id, 'manual', 'Замінена проза', [])
            repo.set_head(scene.id, 'prose', new.id, scene.revision)
            ids = [id for id in context.input_refs if repo.get_version(id).kind == 'manual']
            yield GenerationEvent(type='delta', text=MemorySnapshot(source_prose_ids=ids).model_dump_json())
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scenes[1].id, 'memory', context, Gateway(), threading.Event(), lambda text: None)
    assert attempt.state == 'alternative'
    assert attempt.result_version_id
    assert 'memory' not in repo.get_scene(scenes[1].id).heads


def test_evaluation_window_checks_exact_inputs(tmp_path):
    from storygen.evaluation.story_adapter import build_evaluation_case
    from storygen.storage.snapshots import build_evaluation_snapshot
    repo, story, scenes, _ = setup_memory(tmp_path)
    view = repo.context_view(story.id)
    case = build_evaluation_case(view, story.id, scenes[1].id, 'scene')
    snapshot = build_evaluation_snapshot(view, scenes[1].id, case, 'scene')
    inputs = [d.version for d in case.documents]
    first = repo.save_version(story.id, scenes[1].id, 'evaluation', '{}', inputs)
    repo.update_scene_plan(scenes[5].id, 'Майбутній план', 0)
    assert not repo.publish_evaluation(first.id, view.story.revision, inputs, snapshot).stale
    scene = repo.get_scene(scenes[1].id)
    new = repo.save_version(story.id, scene.id, 'manual', 'Інша', [])
    repo.set_head(scene.id, 'prose', new.id, scene.revision)
    second = repo.save_version(story.id, scene.id, 'evaluation', '{}', inputs)
    assert repo.publish_evaluation(second.id, view.story.revision, inputs, snapshot).stale


@pytest.mark.parametrize('change', ['future_plan','window_brief'])
def test_single_scene_evaluation_window_is_not_whole_story(tmp_path, monkeypatch, change):
    from storygen.evaluation.story_adapter import build_evaluation_case, EvaluationSettings, save_evaluation_settings
    from storygen.evaluation.models import EvaluatorConfig, EvaluationOutcome
    from storygen.generation.worker import RunCoordinator, RunRequest
    repo, story, scenes, _ = setup_memory(tmp_path)
    save_evaluation_settings(repo, story.id, EvaluationSettings(config=EvaluatorConfig(provider='local',model='judge',max_input_chars=100000),context_tokens=128000))
    monkeypatch.setattr('storygen.evaluation.story_adapter.plan_evaluation_windows',lambda view,*args:[build_evaluation_case(view,story.id,scenes[0].id,'scene')])
    def evaluate(*args, **kwargs):
        if change=='future_plan':
            repo.update_scene_plan(scenes[5].id,'Нерелевантний план',0)
        else:
            scene=repo.get_scene(scenes[0].id)
            brief=repo.save_version(story.id,scene.id,'brief','Нове завдання',[])
            repo.set_head(scene.id,'brief',brief.id,scene.revision)
        return EvaluationOutcome(status='incomplete',reasons=['Неповне покриття'])
    monkeypatch.setattr('storygen.evaluation.story_adapter.evaluate',evaluate)
    worker=RunCoordinator(repo)
    run=worker.enqueue(RunRequest(story_id=story.id,mode='evaluate',evaluation_mode='story'),'one-window')
    run.state='running';worker._save(run);worker._execute(run.id)
    assert worker.get_run(run.id).state==('completed' if change=='future_plan' else 'alternative')
    ref=repo.list_versions(story.id,kind='evaluation')[0]
    assert ref.stale==(change=='window_brief')
    assert ref.dependency_snapshot.scene_order==[scenes[0].id]


def test_memory_does_not_inherit_unread_future_plan_from_prose(tmp_path):
    from storygen.storage.snapshots import build_dependency_snapshot
    repo,story,scenes,_=setup_memory(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='fake'))
    view=repo.context_view(story.id)
    baseline=build_dependency_snapshot(view,scenes[1].id,'brief',role,[])
    prose=repo.save_version(story.id,scenes[1].id,'edited','Обрана проза',[],dependency_snapshot=baseline)
    scene=repo.get_scene(scenes[1].id)
    repo.set_head(scene.id,'prose',prose.id,scene.revision)
    context=build_context(repo,scene.id,'memory',role)
    repo.update_scene_plan(scenes[5].id,'Майбутній план',0)
    assert repo.get_version(prose.id).stale
    assert publish(repo,context)[0].state=='completed'
