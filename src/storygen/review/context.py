"""The measured request is the persisted and transmitted request."""
import json
from ..generation.context import ContextBundle,ContextOverflow
from ..providers.models import RoleSettings
from ..impact.models import fingerprint
from .planning import measurement


def build(repo,plan,spec,results):
    body,prediction,chars=measurement(repo,plan,spec,results);role=RoleSettings.model_validate(spec['settings'])
    limit=role.context_tokens-role.max_output_tokens
    if prediction['input_tokens']>limit or chars>role.max_input_chars:raise ContextOverflow(prediction['input_tokens'],limit,chars,max_input_chars=role.max_input_chars)
    return ContextBundle(story_id=plan['story_id'],scene_id=plan['scene_id'],stage='review_part',scene_revision=None,
        story_revision=repo.get_story(plan['story_id']).revision,settings=role,system_text=body['messages'][0]['content'],user_text=body['messages'][1]['content'],
        input_refs=list(dict.fromkeys(id for t in plan['targets'] for id in t['source_hashes'])),fingerprint=fingerprint([plan['id'],spec['id'],body]),
        estimated_tokens=prediction['input_tokens'],estimate_method=prediction['method'],api_request=body,token_estimate=prediction,
        fragments={'review_plan':json.dumps(plan,ensure_ascii=False),'review_spec':json.dumps(spec,ensure_ascii=False),'review_results':json.dumps(results,ensure_ascii=False)})
