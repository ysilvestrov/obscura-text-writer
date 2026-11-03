"""Synthetic book revision through queue, storage, publication and memory audit."""
import json
from storygen.application.exports import export_story
from storygen.storage.integrity import check_integrity
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.worker import RunCoordinator
from storygen.generation.dependencies import save_manual_prose
from storygen.run_models import RunRequest
from storygen.impact.planning import plan_impact
from tests.impact.test_runner import runner


def test_reviewed_prose_exports_without_analysis_or_warning_text(tmp_path):
    repo,story,first,second,ref,worker,run,calls=runner(tmp_path)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
    path=export_story(repo,story.id,'txt',allow_incomplete=True)
    text=path.read_text(encoding='utf-8')
    assert 'Марія згадала лист.' in text
    assert 'Перевірено всі передумови' not in text and 'НЕЗАВЕРШЕНО' not in text
    assert check_integrity(repo.root).ok


def test_memory_semantic_review_preserves_historical_journal_and_forwarding(tmp_path):
    from tests.memory.test_forwarding import seeded
    repo,story,scenes=seeded(tmp_path)
    memory_heads={s.id:repo.get_scene(s.id).heads['memory'] for s in scenes}
    original={id:repo.read_text(id) for id in memory_heads.values()}
    first=repo.get_scene(scenes[0].id)
    save_manual_prose(repo,first.id,repo.read_text(first.heads['prose'])+' Настав вечір.',first.revision)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic'),context_tokens=128000,max_input_chars=1000000),repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx);target=json.loads(ctx.fragments['impact_target']);ids=[c['id'] for c in target['changes'] if c['changed']]
            if ctx.stage=='impact_delta':payload=dict(covered_change_ids=ids,items=[],uncertainty=None)
            else:
                assert ctx.fragments['impact_memory_included']=='true'
                payload=dict(materials=[dict(version_id=target['version_id'],verdict='no_impact',covered_change_ids=ids,explanation='Зміст прози узгоджений.',findings=[])],memory_semantic_impact='none_found',memory_explanation='Нових змістових суперечностей у твердженнях пам’яті не знайдено; джерела історичні.')
            yield GenerationEvent(type='delta',text=json.dumps(payload,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway());plan=plan_impact(repo.context_view(story.id))
    run=worker.enqueue(RunRequest(story_id=story.id,mode='impact',impact_plan_fingerprint=plan.fingerprint),'memory-review')
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    rows=repo.impact('state',story_id=story.id)
    assert rows and all(row['record'].memory_semantic_impact=='none_found' for row in rows)
    assert all(row['memory_evidence_status']=='historical' and row['memory_needs_update'] for row in rows)
    for scene in scenes:
        assert repo.get_scene(scene.id).heads['memory']==memory_heads[scene.id]
        assert repo.read_text(memory_heads[scene.id])==original[memory_heads[scene.id]]
    assert check_integrity(repo.root).ok
