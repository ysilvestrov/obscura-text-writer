import pytest
pytest.importorskip('tokenizers')
from tests.review.test_store import setup
from tests.token_budget.test_local_counter import artifacts
from storygen.authoring.blueprints import get_role_settings,save_role_settings
from storygen.review.planning import prepare_scene,check_specs,measurement
from storygen.token_budget.local_profiles import register,activate


def test_review_counter_is_explicit_bound_and_falls_back(tmp_path):
    from tokenizers import Tokenizer
    repo,story,first,second,ref,run,target=setup(tmp_path/'data')
    role=get_role_settings(repo,story.id)['planner'];role.provider.response_mode='json_schema';role.provider.local_disable_thinking=True
    save_role_settings(repo,story.id,'planner',role,repo.get_story(story.id).revision)
    plan=prepare_scene(repo,second.id);spec=check_specs(repo,plan,{})[0]
    body,_,_=measurement(repo,plan,spec,{})
    t,template=artifacts(tmp_path)
    observed=len(Tokenizer.from_file(str(t)).encode(' '.join(m['content'] for m in body['messages'])+' ',add_special_tokens=False).ids)
    profile=register(repo.root,role.provider.base_url,body,t,template,[dict(request=body,observed_tokens=observed)])
    assert prepare_scene(repo,second.id)['local_token_counter'] is None
    activate(repo.root,profile['id']);plan=prepare_scene(repo,second.id);spec=check_specs(repo,plan,{})[0]
    assert measurement(repo,plan,spec,{})[1]['method']=='qualified_local_tokenizer'
    (repo.root/'local_tokenizers'/profile['id']/'chat-template.txt').write_text('changed',encoding='utf-8')
    fallback=measurement(repo,plan,spec,{})[1]
    assert fallback['method']!='qualified_local_tokenizer'
    assert fallback['reasons']==['local_counter_unavailable']
