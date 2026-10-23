import json
import pytest
from storygen.application.statistics import text_statistics,scene_statistics
from storygen.generation.context import build_context,ContextOverflow
from storygen.providers.models import RoleSettings,ProviderSettings
from storygen.token_budget.core import canonical
from tests.memory.test_forwarding import seeded


def test_unicode_word_counts():
    text="П’ять п'єс, пʼять. Синьо-жовтий — пів‐аркуша і пів‑слова! 😀"
    assert text_statistics(text)=={'characters':len(text),'words':7}
    assert text_statistics('')=={'characters':0,'words':0}
    assert text_statistics('і\u0308жа')=={'characters':4,'words':1}


def test_selected_only_and_memory_prefix(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    repo.save_version(story.id,scenes[1].id,'draft','Альтернатива '*200,[])
    before=repo.get_story(story.id)
    result=scene_statistics(repo,scenes[1].id,'memory')
    assert result['materials']['draft'] is None
    assert result['materials']['prose']['words']==4
    assert result['memory']['previous']['active']['facts']==1
    assert result['memory']['through_scene']['active']['facts']==2
    assert result['memory']['through_scene']['current_scene_events']==1
    assert repo.get_story(story.id)==before


@pytest.mark.parametrize('mode',['prose','patches','diff'])
def test_context_breakdown_exact_body_and_overflow(tmp_path,mode):
    repo,story,scenes=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='offline'),context_tokens=100000,max_input_chars=1000000,edit_mode=mode)
    ctx=build_context(repo,scenes[0].id,'brief',role)
    parts=ctx.context_breakdown['parts']
    assert sum(p['request_bytes'] for p in parts)==len(canonical(ctx.api_request).encode('utf-8'))
    assert sum(p['estimated_tokens'] for p in parts)==ctx.estimated_tokens
    assert ctx.api_request['messages'][1]['content']==ctx.user_text
    tiny=role.model_copy(update={'context_tokens':512,'max_output_tokens':256})
    with pytest.raises(ContextOverflow) as caught:build_context(repo,scenes[0].id,'brief',tiny)
    assert caught.value.breakdown['estimated_input_tokens']>256
    assert caught.value.breakdown['parts']


def test_future_memory_is_unavailable_not_counted(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    scene=repo.get_scene(scenes[0].id)
    bad=repo.save_version(story.id,scene.id,'memory',repo.read_text(scenes[2].heads['memory']),[])
    repo.set_head(scene.id,'memory',bad.id,scene.revision)
    result=scene_statistics(repo,scene.id,'draft')
    assert not result['memory']['through_scene']['available']
    assert 'active' not in result['memory']['through_scene']


@pytest.mark.parametrize('mode',['prose','patches','diff'])
def test_editor_preview_uses_actual_working_source_and_schema(tmp_path,mode):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.editor_loop import context as edit_context
    repo,story,scenes=seeded(tmp_path)
    role=RoleSettings(provider=ProviderSettings(model='offline',response_mode='json_schema'),context_tokens=100000,max_input_chars=1000000,edit_mode=mode)
    save_role_settings(repo,story.id,'editor',role,repo.get_story(story.id).revision)
    if mode=='prose':
        scene=repo.get_scene(scenes[0].id)
        brief=repo.save_version(story.id,scene.id,'brief','{"objective":"Мета","beats":["Дія"],"constraints":[],"proposed_changes":[]}',[])
        repo.set_head(scene.id,'brief',brief.id,scene.revision)
    scene=repo.get_scene(scenes[0].id)
    actual=edit_context(repo,scene.id,role,scene.heads['prose'])
    result=scene_statistics(repo,scene.id,'edit')['context']
    assert result['available'] and result['estimated_input_tokens']==actual.estimated_tokens
    assert not result.get('reason')
    assert result['request_bytes']==len(canonical(actual.api_request).encode('utf-8'))
    if mode=='patches':assert any(p['kind']=='response_schema' for p in result['parts'])
