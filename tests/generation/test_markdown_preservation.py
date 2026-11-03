import threading
import pytest

from tests.generation.test_evidence_protocols import seeded
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.generation.dependencies import save_manual_draft
from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.providers.streaming import GenerationEvent


def test_markdown_instructions_are_in_real_request_and_result_metadata(tmp_path):
    repo,scene=seeded(tmp_path)
    original='Олена побачила **зорі**. Вечір був тихий.'
    source=save_manual_draft(repo,scene.id,original,scene.revision,content_format='markdown')
    scene=repo.get_scene(scene.id)
    settings=RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='diff',edit_review='review')
    context=build_context(repo,scene.id,'edit',settings)
    assert context.fragments['output_content_format']=='markdown'
    assert 'MARKDOWN' in context.system_text
    assert context.api_request['messages'][0]['content']==context.system_text
    assert original in context.user_text
    candidate=original.replace('тихий','тихим')
    class Gateway:
        def stream(self,*args):
            yield GenerationEvent(type='delta',text=candidate)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'edit',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='needs_review',attempt.error
    preview=copyedit_preview(repo,scene.id,attempt.id)
    result=select_copyedits(repo,scene.id,attempt.id,list(range(len(preview['edits']))),preview['expected_revision'],preview['proposal_fingerprint'])
    assert result['version'].content_format=='markdown'
    assert repo.read_text(source.id)==original


def test_new_writer_result_is_markdown_with_declared_contract(tmp_path):
    repo,scene=seeded(tmp_path)
    brief=repo.save_version(scene.story_id,scene.id,'brief','{"objective":"Зорі","beats":["Поглянути вгору"]}',[])
    scene=repo.set_head(scene.id,'brief',brief.id,scene.revision)
    context=build_context(repo,scene.id,'draft',RoleSettings(provider=ProviderSettings(model='fake')))
    assert context.fragments['output_content_format']=='markdown'
    assert 'MARKDOWN' in context.api_request['messages'][0]['content']
    class Gateway:
        def stream(self,*args):
            yield GenerationEvent(type='delta',text='Олена побачила **зорі**.')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'draft',context,Gateway(),threading.Event(),lambda _:None)
    assert repo.get_version(attempt.result_version_id).content_format=='markdown'


def test_cross_sentence_format_delimiters_are_one_acceptance_group():
    from storygen.rewrite_diff import build_rewrite_diff
    from storygen.sentence_groups import sentence_groups,validate_group_selection
    source='Перше речення. Друге речення.'
    proposal=build_rewrite_diff(source,'**'+source+'**')
    assert len(proposal.edits)==2
    groups=sentence_groups(source,proposal,content_format='markdown')
    assert len(groups)==1 and groups[0]['indices']==[0,1]
    with pytest.raises(ValueError):validate_group_selection(source,proposal,[0],content_format='markdown')
    validate_group_selection(source,proposal,[0,1],content_format='markdown')


def test_raw_markdown_evidence_is_not_rebound_to_visible_projection():
    from storygen.evidence import fragment_text
    from storygen.memory.models import MemoryDelta,MemorySnapshot
    from storygen.memory.service import merge_memory_delta
    text='Олена **побачила зорі**.\n\nВечір був _тихим_.'
    fragment=fragment_text(text)[0]
    assert text[fragment.start:fragment.end]==fragment.text
    delta=MemoryDelta.model_validate({'facts':[{'text':'Олена бачила зорі.','evidence_id':fragment.id}]})
    memory=merge_memory_delta(MemorySnapshot(source_prose_ids=[]),delta,'source',text)
    assert memory.facts[0].quote==fragment.text and '**' in memory.facts[0].quote


def test_partial_delimiter_acceptance_is_rejected_before_publication(tmp_path):
    repo,scene=seeded(tmp_path)
    original='Перше речення. Друге речення.'
    save_manual_draft(repo,scene.id,original,scene.revision,content_format='markdown')
    scene=repo.get_scene(scene.id)
    context=build_context(repo,scene.id,'edit',RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='diff',edit_review='review'))
    class Gateway:
        def stream(self,*args):
            yield GenerationEvent(type='delta',text='**'+original+'**')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'edit',context,Gateway(),threading.Event(),lambda _:None)
    preview=copyedit_preview(repo,scene.id,attempt.id)
    assert preview['grouping_version']==2 and preview['groups'][0]['indices']==[0,1]
    with pytest.raises(ValueError):
        select_copyedits(repo,scene.id,attempt.id,[0],preview['expected_revision'],preview['proposal_fingerprint'])
    assert 'prose' not in repo.get_scene(scene.id).heads


def test_editor_loop_working_copies_retain_markdown_format(tmp_path):
    from tests.generation.test_editor_loop import seeded as loop_fixture
    repo,scene,_,worker,run,calls=loop_fixture(tmp_path,['Вона **йшла** до дома. На вулиці тихо.'],mode='diff',limit=1)
    current=repo.get_scene(scene.id)
    save_manual_draft(repo,scene.id,'Вона **йшов** до дома. На вулиці тихо.',current.revision,content_format='markdown')
    worker._execute(run.id)
    run=worker.get_run(run.id)
    assert run.state=='needs_review',run.error
    assert repo.get_version(run.editor_loop['base_version_id']).content_format=='markdown'
    assert repo.get_version(run.editor_loop['current_version_id']).content_format=='markdown'
    assert calls[0].fragments['output_content_format']=='markdown'
