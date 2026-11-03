"""Offline synthetic counter binding for integration tests, never a real model gate."""
from tests.token_budget.test_local_counter import artifacts
from storygen.authoring.blueprints import get_role_settings,save_role_settings
from storygen.review.planning import prepare_scene,check_specs,measurement
from storygen.token_budget.local_profiles import register,activate


def activate_counter4(repo,scene_id):
    from tokenizers import Tokenizer
    story_id=repo.get_scene(scene_id).story_id
    role=get_role_settings(repo,story_id)['planner']
    role.provider.response_mode='json_schema';role.provider.local_disable_thinking=True
    save_role_settings(repo,story_id,'planner',role,repo.get_story(story_id).revision)
    plan=prepare_scene(repo,scene_id,4);spec=check_specs(repo,plan,{})[0]
    body=measurement(repo,plan,spec,{})[0]
    t,template=artifacts(repo.root)
    observed=len(Tokenizer.from_file(str(t)).encode(' '.join(m['content'] for m in body['messages'])+' ',add_special_tokens=False).ids)
    profile=register(repo.root,role.provider.base_url,body,t,template,[dict(request=body,observed_tokens=observed)])
    activate(repo.root,profile['id'])
    return profile
