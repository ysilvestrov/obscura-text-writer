"""Research-only wire preparation; production implementation remains untouched."""
from importlib.resources import files

from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.review.planning import make_spec, registry_for
from storygen.review.wire import request_for


def build_request(case: dict, config: dict) -> dict:
    role=RoleSettings(provider=ProviderSettings(model=config['model'],response_mode='json_schema',local_disable_thinking=True),
                      context_tokens=config.get('context_tokens',131072),max_output_tokens=4096,
                      temperature=0.1,max_input_chars=500000)
    changes=[dict(id=f'premise-{i}',label='Чинні передумови',input_field='prose',input_kind='head',
                  owner_id=f'prior-{i}',old_text=text,new_text=text,changed=False) for i,text in enumerate(case['sources'])]
    target=dict(version_id='synthetic-target',material='prose',text=case['target'],changes=changes)
    plan=dict(targets=[target],basis_modes={'synthetic-target':'current_consistency'},result_cap=4096,
              settings=role.model_dump(),system=files('storygen.generation').joinpath('resources/review_part_uk_v3.txt').read_text(encoding='utf-8'),
              registry=registry_for([target]))
    sources=[key for key,value in plan['registry'].items() if value['kind']=='source' and value['side']=='new']
    targets=[key for key,value in plan['registry'].items() if value['kind']=='target']
    spec=make_spec(plan,'check',sources,targets)
    payload,body,aliases=request_for(plan,spec,{})
    body['stream']=False
    body.pop('stream_options',None)
    return dict(plan=plan,spec=spec,payload=payload,body=body,aliases=aliases)
