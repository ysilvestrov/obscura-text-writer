import threading

import pytest

from storygen.rewrite_diff import build_rewrite_diff, apply_rewrite_diff, RewriteDiff


@pytest.mark.parametrize('before,after', [
    ('Вона йшла. Вона йшла.', 'Вона йшла. Вона тихо йшла.'),
    ('Текст\r\nІ ще текст.', 'Текст\r\nА ще — текст.'),
    ('Її п’ять слів.', 'Її п\'ять слів.'),
    ('Ранок.', 'Тихий ранок.'), ('Це довге слово.', 'Це слово.'),
    ('Без змін.', 'Без змін.'),
    ('🙂 Вона йшов. е\u0301', '🙂 Вона йшла. е\u0301'),
])
def test_diff_round_trip_and_empty_selection(before, after):
    proposal = build_rewrite_diff(before, after)
    assert apply_rewrite_diff(before, proposal) == after
    assert apply_rewrite_diff(before, proposal, []) == before


def test_close_changes_are_one_author_unit_but_paragraphs_stay_separate():
    p = build_rewrite_diff('Лана стояла, руками.\n\nВона йшов.', 'Лана стояла з руками.\n\nВона йшла.')
    assert len(p.edits) == 2
    assert apply_rewrite_diff('Лана стояла, руками.\n\nВона йшов.', p, [0]) == 'Лана стояла з руками.\n\nВона йшов.'


def test_modified_anchor_or_candidate_rejected():
    before = 'Вона йшов.'
    p = build_rewrite_diff(before, 'Вона йшла.')
    for change in ['anchor', 'candidate']:
        raw = p.model_dump()
        if change == 'anchor': raw['edits'][0]['original'] = 'чуже'
        else: raw['candidate_text'] = 'Інший текст.'
        with pytest.raises(ValueError): apply_rewrite_diff(before, RewriteDiff.model_validate(raw))


@pytest.mark.parametrize('fault',['overlap','reverse'])
def test_corrupt_span_order_rejected(fault):
    text='Вона йшов.\n\nВін співаю.'
    p=build_rewrite_diff(text,'Вона йшла.\n\nВін співає.')
    if fault=='reverse':p.edits.reverse()
    else:p.edits[1].start=p.edits[0].start
    with pytest.raises(ValueError):apply_rewrite_diff(text,p)


def test_token_operational_limit_rejects_before_expensive_comparison():
    with pytest.raises(ValueError,match='12000'):
        build_rewrite_diff('а '*6001,'б '*6001)


@pytest.mark.parametrize('count',[400,401])
def test_edit_count_boundary(count):
    source='\n\n'.join(f'old{i}' for i in range(count))
    candidate='\n\n'.join(f'new{i}' for i in range(count))
    if count==401:
        with pytest.raises(ValueError,match='400'):build_rewrite_diff(source,candidate)
    else:
        p=build_rewrite_diff(source,candidate)
        assert len(p.edits)==400 and apply_rewrite_diff(source,p)==candidate


@pytest.mark.parametrize('after', ['', ' '*10, 'a'*80001],ids=['empty','blank','oversize'])
def test_unusable_candidate_rejected(after):
    with pytest.raises(ValueError): build_rewrite_diff('Текст.', after)


def test_new_mode_never_auto_publishes_and_selection_is_cas(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
    from storygen.storage.repository import Repository
    from storygen.generation.context import build_context
    from storygen.providers.models import RoleSettings, ProviderSettings
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Тест'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft','Вона йшов.\n\nТут тихо.',[])
    repo.set_head(scene.id,'draft',draft.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='fake',response_mode='json_schema'),edit_mode='diff',edit_review='auto')
    ctx=build_context(repo,scene.id,'edit',role)
    assert 'response_format' not in ctx.api_request
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text='Вона йшла.\n\nТут дуже тихо.')
            yield GenerationEvent(type='terminal',finish_reason='stop')
    a=execute_stage(repo,scene.id,'edit',ctx,Gateway(),threading.Event(),lambda _:None)
    assert a.state=='needs_review' and not repo.get_scene(scene.id).heads.get('prose')
    preview=copyedit_preview(repo,scene.id,a.id)
    assert preview['protocol_version']==2 and preview['default_selected_indices']==[]
    result=select_copyedits(repo,scene.id,a.id,[0],preview['expected_revision'],preview['proposal_fingerprint'])
    assert repo.read_text(result['version'].id)=='Вона йшла.\n\nТут тихо.'
    assert repo.read_text(draft.id)=='Вона йшов.\n\nТут тихо.'
    newer=repo.save_version(story.id,scene.id,'draft','Інша чернетка.',[])
    repo.set_head(scene.id,'draft',newer.id,repo.get_scene(scene.id).revision)
    with pytest.raises((ValueError,RevisionConflict)):
        select_copyedits(repo,scene.id,a.id,[],repo.get_scene(scene.id).revision,preview['proposal_fingerprint'])


def test_effort_wire_and_conflicting_flags():
    from storygen.providers.models import ProviderSettings
    from storygen.providers.requests import venice_reasoning
    p=ProviderSettings(provider='venice',model='fake',venice_reasoning_effort='low')
    assert venice_reasoning(p)=={'reasoning':{'effort':'low'}}
    with pytest.raises(ValueError):
        ProviderSettings(provider='venice',model='fake',venice_disable_thinking=True,venice_reasoning_effort='low')
