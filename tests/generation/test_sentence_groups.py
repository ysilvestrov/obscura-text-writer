import pytest

from storygen.rewrite_diff import build_rewrite_diff
from storygen.sentence_groups import sentence_groups, validate_group_selection


SOURCE='Олена працювала, її руки вкривало лагідне осіннє вечірнє світло, але голос лишався спокійним.'
CANDIDATE='Олена працювала, світло вкривало лагідне осіннє вечірнє її руки, але голос лишався спокійним.'


def joined(parts):return ''.join(part['text'] for part in parts)


def test_distant_changes_in_sentence_are_one_atomic_group():
    proposal=build_rewrite_diff(SOURCE,CANDIDATE)
    assert len(proposal.edits)>=2
    groups=sentence_groups(SOURCE,proposal)
    assert len(groups)==1
    assert groups[0]['indices']==list(range(len(proposal.edits)))
    assert joined(groups[0]['before_parts'])==SOURCE
    assert joined(groups[0]['after_parts'])==CANDIDATE
    assert any(not part['changed'] and 'вкривало' in part['text'] for part in groups[0]['after_parts'])
    with pytest.raises(ValueError,match='речення'):validate_group_selection(SOURCE,proposal,[0])
    validate_group_selection(SOURCE,proposal,[])
    validate_group_selection(SOURCE,proposal,list(range(len(proposal.edits))))


@pytest.mark.parametrize('separator',['. ','!\r\n','?\n\n','!» '])
def test_different_sentences_remain_separate(separator):
    before='Вона йшов'+separator+'Він співаю.'
    after='Вона йшла'+separator+'Він співає.'
    proposal=build_rewrite_diff(before,after)
    groups=sentence_groups(before,proposal)
    assert len(groups)==2
    validate_group_selection(before,proposal,groups[0]['indices'])


def test_legacy_patches_are_grouped_without_rewriting_proposal():
    from storygen.copyediting import CopyEdits
    proposal=CopyEdits.model_validate({'edits':[
        dict(fragment_id='f000001',original='її руки',replacement='світло',category='grammar'),
        dict(fragment_id='f000001',original='світло',replacement='її руки',category='wording')]})
    old=proposal.model_dump()
    groups=sentence_groups(SOURCE,proposal)
    assert len(groups)==1 and joined(groups[0]['after_parts'])==CANDIDATE
    assert proposal.model_dump()==old
    assert groups[0]['category']=='mixed'


def generated(tmp_path,mode):
    import json,threading
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.context import build_context
    from storygen.generation.stages import execute_stage
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Одна правка'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft',SOURCE,[]);repo.set_head(scene.id,'draft',draft.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='synthetic'),edit_mode=mode,edit_review='review')
    raw=CANDIDATE if mode=='diff' else json.dumps({'edits':[
        dict(fragment_id='f000001',original='її руки',replacement='світло',category='grammar'),
        dict(fragment_id='f000001',original='світло',replacement='її руки',category='grammar')]})
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'edit',build_context(repo,scene.id,'edit',role),Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='needs_review',attempt.error
    return repo,scene,attempt


@pytest.mark.parametrize('mode',['patches','diff'])
def test_partial_group_is_rejected_by_preview_service_and_storage(tmp_path,mode):
    from storygen.generation.copyedit_review import copyedit_preview,select_copyedits,selection_preview
    from storygen.copyediting import proposal_data,apply_proposal
    repo,scene,attempt=generated(tmp_path,mode)
    preview=copyedit_preview(repo,scene.id,attempt.id)
    raw=repo.get_attempt(attempt.id).context['copyedit_proposal'].copy()
    assert len(preview['groups'])==1 and len(preview['groups'][0]['indices'])>=2
    arguments=(preview['expected_revision'],preview['proposal_fingerprint'])
    with pytest.raises(ValueError,match='речення'):select_copyedits(repo,scene.id,attempt.id,[0],*arguments)
    with pytest.raises(ValueError,match='речення'):selection_preview(repo,scene.id,attempt.id,[0],*arguments)
    _,original,proposal,_,_=proposal_data(repo.context_view(scene.story_id),attempt)
    from storygen.dependency_models import DependencySnapshot
    partial=repo.save_version(scene.story_id,scene.id,'edited',apply_proposal(original,proposal,[0]),attempt.context['input_refs'],dependency_snapshot=DependencySnapshot.model_validate(attempt.context['dependency_snapshot']))
    with pytest.raises(ValueError,match='речення'):
        repo.commit_copyedit_selection(attempt.id,partial,[0],*arguments,[])
    assert 'prose' not in repo.get_scene(scene.id).heads
    assert repo.get_attempt(attempt.id).context['copyedit_proposal']==raw
    full=select_copyedits(repo,scene.id,attempt.id,preview['groups'][0]['indices'],*arguments)
    assert repo.read_text(full['version'].id)==CANDIDATE


@pytest.mark.parametrize('before,after',[
    ('🙂 Вона йшов довго поміж тихих дерев, а потім вернувся.','🙂 Вона йшла довго поміж тихих дерев, а потім вернулася.'),
    ('Ранок. Вона йшла тихо.','Ранок. І вона йшла дуже тихо.'),
    ('Вона йшла дуже довго, але кроки були зовсім тихими.','Вона йшла довго, але кроки були тихими.'),
    ('Вона чекала. Потім пішла.','Вона чекала, потім пішла.'),
])
def test_group_parts_preserve_unicode_insertions_and_cross_sentence_edits(before,after):
    proposal=build_rewrite_diff(before,after)
    groups=sentence_groups(before,proposal)
    assert groups
    validate_group_selection(before,proposal,list(range(len(proposal.edits))))
    for group in groups:
        assert joined(group['before_parts']) in before
        assert joined(group['after_parts']) in after


def test_historical_partial_decision_is_read_without_rewriting(tmp_path):
    from storygen.copyediting import proposal_data,apply_proposal,record_decision
    from storygen.generation.copyedit_review import copyedit_preview
    repo,scene,attempt=generated(tmp_path,'diff')
    _,original,proposal,_,_=proposal_data(repo.context_view(scene.story_id),attempt)
    from storygen.dependency_models import DependencySnapshot
    ref=repo.save_version(scene.story_id,scene.id,'edited',apply_proposal(original,proposal,[0]),attempt.context['input_refs'],dependency_snapshot=DependencySnapshot.model_validate(attempt.context['dependency_snapshot']))
    repo.set_head(scene.id,'prose',ref.id,repo.get_scene(scene.id).revision)
    record_decision(attempt,repo.get_scene(scene.id),[0],ref.id,'manual',[])
    attempt.state='completed';attempt.result_version_id=ref.id;repo.save_attempt(attempt)
    old=repo.get_attempt(attempt.id).model_dump()
    preview=copyedit_preview(repo,scene.id,attempt.id)
    assert preview['can_apply'] and len(preview['groups'])==1
    assert preview['decisions'][-1]['selected_indices']==[0]
    assert repo.get_attempt(attempt.id).model_dump()==old
