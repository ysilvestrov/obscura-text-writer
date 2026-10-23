from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.providers.requests import generation_request,sdk_arguments,evaluation_request
from storygen.evaluation.models import EvaluatorConfig
from types import SimpleNamespace


def test_venice_disable_thinking_controls_exact_request_and_sdk():
    role=RoleSettings(provider=ProviderSettings(provider='venice',model='qwen-3-8-27b',venice_disable_thinking=True))
    body=generation_request('edit',role,'Система','Текст',{})
    assert body['reasoning']=={'enabled':False}
    assert body['venice_parameters']['disable_thinking'] is True
    args=sdk_arguments(body)
    assert args['extra_body']['reasoning']=={'enabled':False}
    assert 'reasoning' not in args
    role.provider.venice_disable_thinking=False
    assert 'reasoning' not in generation_request('edit',role,'Система','Текст',{})


def test_evaluator_uses_same_reasoning_contract():
    config=EvaluatorConfig(provider='venice',model='test',max_input_chars=10000,venice_disable_thinking=True)
    request=SimpleNamespace(messages=[],max_output_tokens=100,temperature=None,response_mode='prompt_json')
    assert evaluation_request(config,request)['reasoning']=={'enabled':False}


def test_reasoning_wire_contract_is_in_evaluator_admission_identity(monkeypatch):
    from storygen.evaluation.runner import evaluator_fingerprint
    from storygen.evaluation.prompting import load_rubric
    from storygen.providers import requests
    config=EvaluatorConfig(provider='venice',model='test',max_input_chars=10000,venice_disable_thinking=True)
    before=evaluator_fingerprint(config,load_rubric())
    monkeypatch.setattr(requests,'venice_reasoning',lambda settings: {'reasoning':{'enabled':True}})
    assert evaluator_fingerprint(config,load_rubric())!=before
