import json
import pytest
from storygen.impact.chunking import plan_chunks,task_payload
from storygen.generation.impact_chunk_context import build_chunk_context
from storygen.impact.models import fingerprint,ImpactPlan
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings,ProviderSettings
from tests.impact.test_runner import runner


def large_plan(root):
    repo,story,first,second,ref,worker,run,calls=runner(root)
    from storygen.impact.planning import plan_impact
    plan=plan_impact(repo.context_view(story.id))
    target=plan.targets[0]
    changes=list(target.changes)
    change=next(c for c in changes if c.changed)
    changes[changes.index(change)]=change.model_copy(update={'old_text':('Ранок і тиша. 😀 '*500),'new_text':('Вечір і лист. 😀 '*500)})
    target=target.model_copy(update={'changes':changes,'text':'Марія читає лист. 😀 '*900})
    target.group_id=fingerprint([c.model_dump() for c in sorted(changes,key=lambda c:c.id) if c.changed])
    target.fingerprint=fingerprint(target.model_dump(exclude={'fingerprint','group_id','memory_id','memory_sha256','memory_text','memory_source_hashes','memory_evidence_status'}))
    plan=ImpactPlan(story_id=story.id,targets=[target],fingerprint=fingerprint([target.fingerprint]))
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='synthetic-impact'),context_tokens=24000,max_output_tokens=2048,max_input_chars=13000),repo.get_story(story.id).revision)
    return repo,plan


def test_unicode_and_large_source(tmp_path):
    repo,plan=large_plan(tmp_path)
    manifest=plan_chunks(repo,plan)
    assert manifest.protocol==2
    assert manifest==plan_chunks(repo,plan)
    assert len(manifest.tasks)>3
    for key,spans in manifest.coverage.items():
        text=manifest.documents[key]
        assert spans[0][0]==0 and spans[-1][1]==len(text)
        assert all(left[1]==right[0] for left,right in zip(spans,spans[1:]))
    for task in manifest.tasks:
        ctx=build_chunk_context(repo,manifest,task,{},planning=True)
        assert ctx.estimated_tokens<=ctx.settings.context_tokens-ctx.settings.max_output_tokens
        assert len(json.dumps(ctx.api_request,ensure_ascii=False,separators=(',',':')))<=ctx.settings.max_input_chars
    assert any(t['phase']=='reduce_check' for t in manifest.tasks)


def test_dedup_preserves_identity(tmp_path):
    repo,plan=large_plan(tmp_path)
    t=plan.targets[0];c=t.changes[0]
    t.changes.append(c.model_copy(update={'id':'different-identity','owner_id':'another','changed':False,'new_text':c.old_text}))
    manifest=plan_chunks(repo,plan)
    assert len(manifest.documents)<sum(2 for c in t.changes)+2
    units=[u for u in manifest.units.values() if u['change_id']=='different-identity']
    assert units and {u['side'] for u in units}=={'old','new'}
    payload=next(task_payload(manifest,task,{},planning=True) for task in manifest.tasks if task['phase']=='check')
    assert 'documents' in payload and all(isinstance(text,str) for text in payload['documents'].values())


def test_manifest_changes_with_limits(tmp_path):
    repo,plan=large_plan(tmp_path)
    first=plan_chunks(repo,plan)
    role=first.settings.model_copy(update={'max_input_chars':15000})
    save_role_settings(repo,plan.story_id,'planner',role,repo.get_story(plan.story_id).revision)
    assert first.fingerprint!=plan_chunks(repo,plan).fingerprint


def test_native_schema_is_part_result():
    from storygen.providers.requests import generation_request
    from storygen.impact.chunk_models import PartResult
    settings=RoleSettings(provider=ProviderSettings(model='synthetic-impact',response_mode='json_schema'))
    request=generation_request('impact_part',settings,'system','user',{})
    schema=request['response_format']['json_schema']['schema']
    assert set(schema['properties'])==set(PartResult.model_fields)
    assert 'materials' not in schema['properties']
