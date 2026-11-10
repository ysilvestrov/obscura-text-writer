"""MEMORY-SELECT in the request: selection only on overflow, the whole request measured, the core never cut (#60)."""
import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import SELECTED_PROJECTION, ContextOverflow, build_context
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import project_memory
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository

HEADER='ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ\n'


def story_with_memory(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Відбір'))
    first=repo.create_scene(story.id,SceneCreate(title='1',beats='Вдома',character_ids=['A']))
    second=repo.create_scene(story.id,SceneCreate(title='2',beats='Маяк і стара карта',character_ids=['A','B']))
    prose=repo.save_version(story.id,first.id,'manual','Анна вдома в халаті.',[])
    repo.set_head(first.id,'prose',prose.id,repo.get_scene(first.id).revision)
    events=[_add_event('character_states','Синій халат',prose.id,'в халаті',0,['A'],slot='clothing')]
    events+=[_add_event('facts',f'Подія на узбережжі номер {n}: довгий опис того, що сталося біля води',prose.id,'вдома',n) for n in range(25)]
    events+=[_add_event('character_states',f'Борис тримає річ номер {n}',prose.id,'вдома',100+n,['B']) for n in range(10)]
    events+=[_add_event('facts','Маяк стоїть на старій карті',prose.id,'вдома',200)]
    events+=[_add_event('timeline',f'Сталася подія {n}',prose.id,'вдома',300+n) for n in range(5)]
    journal=MemoryJournal(schema_version=3,source_prose_ids=[prose.id],events=events)
    memory=repo.save_version(story.id,first.id,'memory',journal.model_dump_json(),[prose.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    return repo,second,journal,prose


def settings(**values):
    return RoleSettings(provider=ProviderSettings(model='test'),**{'context_tokens':262144,**values})


def memory_section(context):
    return context.user_text.split(HEADER)[1].split('\n\nЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ')[0]


def test_fitting_request_is_unchanged(tmp_path):
    repo,scene,journal,prose=story_with_memory(tmp_path)
    context=build_context(repo,scene.id,'brief',settings())
    expected=project_memory(journal,['A','B'],{prose.id:1},tracked=['A'],names={})
    assert memory_section(context)==expected.text
    assert context.memory_metrics['projection_version']=='memory-uk-v3' and 'selection' not in context.memory_metrics
    assert not any('Повна пам’ять не вміщається' in w for w in context.context_warnings)


def test_char_limit_selects_memory_and_keeps_the_core(tmp_path):
    repo,scene,journal,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings())
    limit=len(full.system_text)+len(full.user_text)-400
    context=build_context(repo,scene.id,'brief',settings(max_input_chars=limit))
    assert len(context.system_text)+len(context.user_text)<=limit
    section=memory_section(context)
    assert section.startswith('ЯДРО СТАНУ — протагоніст\nодяг: Синій халат')
    selection=context.memory_metrics['selection']
    assert context.memory_metrics['projection_version']==SELECTED_PROJECTION
    assert context.memory_metrics['projection_chars']==len(section)
    assert sum(selection['dropped'].values())>0 and selection['layers']['core']==1
    assert len(selection['selected_claim_ids'])==sum(selection['layers'].values())
    assert 0<selection['steps']<=12 and selection['char_budget']>=len(section)
    assert any('Повна пам’ять не вміщається' in w for w in context.context_warnings)
    # 400 chars are cut from unmatched entries; the plan words rank the matching fact through FTS, so it stays.
    lighthouse=next(e.claim_id for e in journal.events if e.text=='Маяк стоїть на старій карті')
    assert 'Маяк стоїть на старій карті' in section and lighthouse in selection['selected_claim_ids']


def test_token_limit_selects_memory(tmp_path):
    repo,scene,_,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings(max_output_tokens=512))
    context=build_context(repo,scene.id,'brief',settings(max_output_tokens=512,context_tokens=full.estimated_tokens+512-200))
    assert context.estimated_tokens<=full.estimated_tokens-200
    assert context.memory_metrics['projection_version']==SELECTED_PROJECTION
    assert context.fingerprint!=full.fingerprint


def test_whole_request_is_measured_with_a_nonlinear_estimate(tmp_path,monkeypatch):
    # A profile valid only inside [min_bytes, max_bytes] makes per-part estimates non-additive; selection re-measures the
    # whole request, so whatever budget it picks passes the same check that raises ContextOverflow.
    import storygen.token_budget.service as service
    real=service.token_estimate
    def stepped(repo,provider,base_url,request):
        prediction=real(repo,provider,base_url,request)
        body=prediction['body_bytes']
        return {**prediction,'input_tokens':body//3 if body<5000 else body+256}
    monkeypatch.setattr(service,'token_estimate',stepped)
    repo,scene,_,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings(max_output_tokens=512))
    assert full.estimated_tokens>3000
    context=build_context(repo,scene.id,'brief',settings(max_output_tokens=512,context_tokens=3000+512))
    assert context.estimated_tokens<=3000 and context.memory_metrics['projection_version']==SELECTED_PROJECTION


def test_core_that_does_not_fit_is_an_explicit_error(tmp_path):
    repo,scene,_,_=story_with_memory(tmp_path)
    with pytest.raises(ContextOverflow) as error:
        build_context(repo,scene.id,'brief',settings(max_output_tokens=512,context_tokens=900))
    assert 'мінімальна пам’ять' in str(error.value) and 'ядро не обрізається' in str(error.value)


def test_selection_is_deterministic(tmp_path):
    repo,scene,_,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings())
    limit=len(full.system_text)+len(full.user_text)-400
    first=build_context(repo,scene.id,'brief',settings(max_input_chars=limit))
    second=build_context(repo,scene.id,'brief',settings(max_input_chars=limit))
    assert first.user_text==second.user_text and first.memory_metrics==second.memory_metrics


def test_failing_minimum_still_probes_the_largest_budget(tmp_path,monkeypatch):
    # Below a profile's byte range the fallback overestimates: the core-only request is estimated higher than a larger
    # one inside the range. Selection must not report ContextOverflow while a probed budget fits.
    import storygen.token_budget.service as service
    real=service.token_estimate;bodies=[];threshold=[None]
    def stepped(repo,provider,base_url,request):
        prediction=real(repo,provider,base_url,request)
        body=prediction['body_bytes'];bodies.append(body)
        inside=threshold[0] is None or body>=threshold[0]
        return {**prediction,'input_tokens':body//3 if inside else body+256}
    monkeypatch.setattr(service,'token_estimate',stepped)
    repo,scene,_,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings(max_output_tokens=512))
    full_chars=len(full.system_text)+len(full.user_text)
    limit=bodies[-1]//3+10
    tight=settings(max_output_tokens=512,max_input_chars=full_chars-400,context_tokens=600+512)
    with pytest.raises(ContextOverflow):build_context(repo,scene.id,'brief',tight)
    threshold[0]=min(bodies)+1  # the core-only request is the smallest body: only it falls below the profile's range
    context=build_context(repo,scene.id,'brief',settings(max_output_tokens=512,context_tokens=limit+512,max_input_chars=full_chars-400))
    assert context.memory_metrics['projection_version']==SELECTED_PROJECTION
    assert context.estimated_tokens<=limit and len(context.system_text)+len(context.user_text)<=full_chars-400


def test_minimal_overflow_breakdown_measures_the_reduced_request(tmp_path):
    repo,scene,_,_=story_with_memory(tmp_path)
    full=build_context(repo,scene.id,'brief',settings())
    memory=full.memory_metrics['projection_chars']
    with pytest.raises(ContextOverflow) as error:
        build_context(repo,scene.id,'brief',settings(max_input_chars=len(full.system_text)+len(full.user_text)-memory+5))
    parts={p['kind']:p for p in error.value.breakdown['parts']}
    assert all(p['request_bytes']>=0 and p['estimated_tokens']>=0 for p in parts.values())
    assert sum(p['request_bytes'] for p in parts.values())==error.value.breakdown['request_bytes']
