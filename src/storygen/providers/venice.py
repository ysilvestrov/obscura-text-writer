"""Venice catalog policy: only explicitly uncensored, online text models."""
from .models import ModelOption


class VeniceModelUnavailable(ValueError):
    pass


def uncensored_models(client):
    result=[]
    for model in client.models.list(extra_query={'type':'text'}):
        spec=getattr(model,'model_spec',None)
        if not isinstance(spec,dict) or spec.get('uncensored') is not True or spec.get('offline',False) is not False:
            continue
        result.append((model.id,spec))
    return result


def model_options(client):
    return [ModelOption(id=id,context_tokens=spec.get('availableContextTokens'),uncensored=True) for id,spec in uncensored_models(client)]


def validate_model(client,model_id,requires_schema):
    spec=next((spec for id,spec in uncensored_models(client) if id==model_id),None)
    if spec is None:
        raise VeniceModelUnavailable('Venice: модель не має uncensored=true або недоступна в каталозі.')
    if requires_schema and spec.get('capabilities',{}).get('supportsResponseSchema') is not True:
        raise VeniceModelUnavailable('Venice: модель не підтримує JSON Schema. Змініть модель або режим відповіді.')
