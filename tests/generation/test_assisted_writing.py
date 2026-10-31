import threading
import pytest
from storygen.generation.assisted_writing import build_rewrite_context
from storygen.generation.stages import execute_stage
from storygen.providers.streaming import GenerationEvent

class Gateway:
    def __init__(self,text,reason='stop',refusal=False,action=None):self.text=text;self.reason=reason;self.refusal=refusal;self.action=action;self.calls=0
    def stream(self,context,cancel):
        self.calls+=1
        if self.action:self.action()
        if self.text:yield GenerationEvent(type='delta',text=self.text)
        yield GenerationEvent(type='terminal',finish_reason=self.reason,refusal=self.refusal,usage={'prompt_tokens':100,'completion_tokens':20})

def test_one_saved_context_plain_response_and_no_brief(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    assert ctx.stage=='rewrite' and ctx.settings.provider.model=='fake-writer'
    assert 'response_format' not in ctx.api_request
    assert notes.general in ctx.user_text and notes.comments[0].instruction in ctx.user_text
    assert repo.read_text(source.id) in ctx.user_text
    assert ctx.fragments['rewrite_notes']==notes.model_dump_json()
    assert ctx.dependency_snapshot.scope=='author_rewrite'
    assert ctx.dependency_snapshot.frozen_author_source_id==source.id
    gateway=Gateway('Вечір був **тихим**. Вона поспішала додому.')
    attempt=execute_stage(repo,scene.id,'rewrite',ctx,gateway,threading.Event(),lambda _:None)
    assert gateway.calls==1 and attempt.state=='needs_review'
    assert attempt.context['rewrite_proposal']['source_id']==source.id
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert repo.get_comment_set(scene.id).id==notes.id

@pytest.mark.parametrize('text,reason,refusal,state',[('', 'stop',False,'failed'),('частина','length',False,'failed'),('I cannot help with this request.','stop',True,'failed'),('Вечір був **тихим**. Вона йшла додому.','stop',False,'completed')])
def test_non_proposal_results_do_not_replace_source(rewrite_case,text,reason,refusal,state):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    attempt=execute_stage(repo,scene.id,'rewrite',ctx,Gateway(text,reason,refusal),threading.Event(),lambda _:None)
    assert attempt.state==state and not attempt.context.get('rewrite_proposal')
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert repo.get_comment_set(scene.id).id==notes.id

@pytest.mark.parametrize('field,value',[('source_version_id','other'),('comment_set_id','other'),('comment_fingerprint','0'*64)])
def test_changed_inputs_block_context(rewrite_case,field,value):
    repo,_,_,_,_,request=rewrite_case
    with pytest.raises((ValueError,KeyError)):build_rewrite_context(repo,request.model_copy(update={field:value}))


def test_note_change_during_call_is_alternative(rewrite_case):
    from storygen.authoring.comments import CommentPayload
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    def change():
        repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',repo.get_scene(scene.id).revision,notes.revision,
            CommentPayload(general='Інша вказівка.'),expected_source_version_id=source.id)
    attempt=execute_stage(repo,scene.id,'rewrite',ctx,Gateway('Вечір був тихим. Вона поспішала додому.',action=change),threading.Event(),lambda _:None)
    assert attempt.state=='alternative'
    assert attempt.context['fragments']['rewrite_notes']==notes.model_dump_json()
    assert repo.get_comment_set(scene.id).general=='Інша вказівка.'


def test_cancel_and_empty_output_have_no_review(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    ctx=build_rewrite_context(repo,request)
    cancel=threading.Event();cancel.set()
    result=execute_stage(repo,scene.id,'rewrite',ctx,Gateway('Зміна.'),cancel,lambda _:None)
    assert result.state=='cancelled' and not result.context.get('rewrite_proposal')
    result=execute_stage(repo,scene.id,'rewrite',ctx,Gateway(''),threading.Event(),lambda _:None)
    assert result.context['rewrite_failure']['category']=='empty_output'
    assert 'finish_reason=stop' in result.error


def test_empty_notes_and_pending_anchor_block_before_call(rewrite_case):
    from storygen.authoring.comments import CommentPayload,comment_fingerprint
    repo,scene,source,notes,role,request=rewrite_case
    pending=notes.comments[0].model_dump();pending['anchor'].update(state='needs_review',reason='text_changed')
    saved=repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',scene.revision,notes.revision,CommentPayload(comments=[pending]),expected_source_version_id=source.id)
    changed=request.model_copy(update={'comment_set_id':saved['comment_set'].id,'comment_fingerprint':comment_fingerprint(saved['comment_set'],source)})
    with pytest.raises(ValueError,match='переприв’яжіть'):build_rewrite_context(repo,changed)
    empty=repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',scene.revision,saved['comment_set'].revision,CommentPayload(),expected_source_version_id=source.id)['comment_set']
    changed=request.model_copy(update={'comment_set_id':empty.id,'comment_fingerprint':comment_fingerprint(empty,source)})
    with pytest.raises(ValueError,match='хоча б одну'):build_rewrite_context(repo,changed)
