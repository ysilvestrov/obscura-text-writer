import json
import threading

import pytest

from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent
from tests.generation.test_evidence_protocols import seeded


def run_output(tmp_path,raw,mode='patches'):
    repo,scene=seeded(tmp_path)
    context=build_context(repo,scene.id,'edit',RoleSettings(provider=ProviderSettings(model='fake'),edit_mode=mode,edit_review='review'))
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'edit',context,Gateway(),threading.Event(),lambda _:None)
    return repo,scene,attempt


@pytest.mark.parametrize('mode',['patches','diff'])
@pytest.mark.parametrize('raw',['',' \n\t'])
def test_truly_empty_editor_output_has_concrete_error_and_no_result(tmp_path,mode,raw):
    repo,scene,attempt=run_output(tmp_path,raw,mode)
    assert attempt.state=='failed' and not attempt.result_version_id
    assert attempt.context['editor_failure']['category']=='empty_output'
    assert 'порожню відповідь' in attempt.error
    assert not attempt.context.get('copyedit_proposal')


def test_identical_diff_output_is_not_a_review_proposal(tmp_path):
    source_repo,source_scene=seeded(tmp_path/'source')
    original=source_repo.read_text(source_scene.heads['draft'])
    repo,scene,attempt=run_output(tmp_path/'run',original,'diff')
    assert attempt.state=='failed' and attempt.context['editor_failure']['category']=='no_changes'
    assert not attempt.context.get('copyedit_proposal')
    assert not attempt.result_version_id


def test_empty_real_api_stream_is_diagnosed_without_publishing(tmp_path):
    import httpx
    from storygen.providers.streaming import build_generation_gateway
    from tests.providers.test_streaming import stream_response,chunk
    repo,scene=seeded(tmp_path)
    ctx=build_context(repo,scene.id,'edit',RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='diff'))
    usage={'completion_tokens':8879,'completion_tokens_details':{'reasoning_tokens':8876}}
    chunks=[chunk(finish='stop'),{'id':'r','object':'chat.completion.chunk','created':0,'model':'fake','choices':[],'usage':usage}]
    with httpx.Client(transport=httpx.MockTransport(lambda _:stream_response(chunks))) as http:
        gateway=build_generation_gateway(ctx.settings.provider,http_client=http)
        attempt=execute_stage(repo,scene.id,'edit',ctx,gateway,threading.Event(),lambda _:None)
    assert attempt.state=='failed' and attempt.context['editor_failure']['category']=='empty_output'
    assert 'порожню відповідь' in attempt.error and not attempt.result_version_id
    assert 'finish_reason=stop' in attempt.error and '8876 із 8879' in attempt.error
    assert repo.get_attempt(attempt.id).error==attempt.error


@pytest.mark.parametrize('prefix,suffix',[('```json\n','\n```'),('```\n','\n```'),('\n```JSON\n','\n```\n')])
def test_exact_outer_fence_is_recorded_without_rewriting_raw(tmp_path,prefix,suffix):
    raw=prefix+json.dumps({'edits':[dict(fragment_id='f000001',original='ваші',replacement='ваша',category='grammar')]})+suffix
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='needs_review'
    assert len(attempt.context['copyedit_proposal']['proposal']['edits'])==1
    assert attempt.context['editor_warnings']
    assert repo.files.read_partial(attempt.partial_path)==raw
    assert not repo.get_scene(scene.id).heads.get('prose')


@pytest.mark.parametrize('raw',[
    'Ось відповідь:\n```json\n{"edits":[]}\n```',
    '```json\n{"edits":[]}\n```\nПояснення',
    '```json\n{"edits":[]}\n```\n```json\n{"edits":[]}\n```',
    '{"edits":[],"edits":[]}',
    '{"edits":[],"private":NaN}',
])
def test_untrusted_wrappers_and_duplicate_keys_are_not_repaired(tmp_path,raw):
    repo,_,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed'
    assert attempt.context['editor_failure']['category']=='json'
    assert 'Помилка редактора' in attempt.error
    assert repo.files.read_partial(attempt.partial_path)==raw


@pytest.mark.parametrize('payload,part',[
    ({'edits':[dict(fragment_id='f000001',original='два',replacement='три',category='wording')]},'числов'),
    ({'edits':[dict(fragment_id='f000001',original='відсутній якір',replacement='новий',category='grammar')]},'якір'),
    ({'edits':[dict(fragment_id='f000001',original='ваші',replacement='ваша',category='PRIVATE_MODEL_VALUE')]},'category'),
])
def test_editor_errors_explain_trusted_rule_without_echoing_values(tmp_path,payload,part):
    _,_,attempt=run_output(tmp_path,json.dumps(payload))
    assert attempt.state=='failed' and part in attempt.error
    assert 'PRIVATE_MODEL_VALUE' not in attempt.error
    assert attempt.context['editor_failure']['category'] in {'schema','guard'}


def test_invalid_wrapped_proposal_keeps_normalization_warning_and_schema_error(tmp_path):
    raw='```json\n'+json.dumps({'edits':[dict(fragment_id='f000001',original='два',replacement='три',category='UNKNOWN')]})+'\n```'
    _,_,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed' and attempt.context['editor_failure']['category']=='schema'
    assert attempt.context['editor_warnings']


def test_worker_surfaces_editor_normalization_warning(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import RunRequest
    repo,scene=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches',edit_review='review')
    save_role_settings(repo,scene.story_id,'editor',role,repo.get_story(scene.story_id).revision)
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text='```json\n{"edits":[]}\n```')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='stage',stage='edit'),'wrapped')
    worker._execute(run.id)
    assert worker.get_run(run.id).warning
    assert any(e.type=='context_warning' and 'обгортку' in e.data['warnings'][0] for e in repo.list_run_events(run.id))


def test_excessive_json_depth_is_failed_not_left_running(tmp_path):
    raw='{"edits":'+'['*3000+'0'+']'*3000+'}'
    repo,_,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed'
    assert repo.get_attempt(attempt.id).state=='failed'
    assert attempt.context['editor_failure']['category']=='json'
    assert 'глибин' in attempt.error


@pytest.mark.parametrize('original,fragment,reason',[
    ('НЕТOЧНО СКОПІЙОВАНО','f000001','original_missing'),
    ('ваші','f999999','fragment_missing'),
])
def test_anchor_diagnostics_identify_patch_without_echoing_prose(tmp_path,original,fragment,reason):
    payload={'edits':[
        dict(fragment_id='f000001',original='ваші',replacement='ваша',category='grammar'),
        dict(fragment_id=fragment,original=original,replacement='заміна',category='wording')]}
    repo,scene,attempt=run_output(tmp_path,json.dumps(payload,ensure_ascii=False))
    failure=attempt.context['editor_failure']
    assert failure['anchor_reason']==reason and failure['edit_index']==2
    assert failure['fragment_id']==fragment and failure['edit_count']==2
    assert 'Правка 2 із 2' in attempt.error
    assert ('дослівний' if reason=='original_missing' else 'відсутній фрагмент') in attempt.error
    assert 'diff' in attempt.error and original not in attempt.error
    assert not attempt.result_version_id and not repo.get_scene(scene.id).heads.get('prose')


def test_ambiguous_anchor_and_untrusted_fragment_id_diagnostics():
    from storygen.copyediting import CopyEdits,apply_copyedits
    from storygen.generation.editor_output import editor_failure
    for fragment,reason in [('f000001','original_ambiguous'),('PRIVATE_MODEL_TEXT','fragment_missing')]:
        proposal=CopyEdits(edits=[dict(fragment_id=fragment,original='слово',replacement='вираз',category='wording')])
        with pytest.raises(ValueError) as caught:apply_copyedits('слово та слово.',proposal)
        failure=editor_failure(caught.value)
        assert failure['anchor_reason']==reason and 'PRIVATE_MODEL_TEXT' not in failure['message']
