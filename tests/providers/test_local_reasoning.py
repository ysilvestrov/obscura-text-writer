from types import SimpleNamespace
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.requests import generation_request, evaluation_request
from storygen.evaluation.models import EvaluatorConfig


def test_local_thinking_is_opt_in_and_local_only():
    for provider in ['local','venice','openrouter']:
        for enabled in [False,True]:
            settings=RoleSettings(provider=ProviderSettings(provider=provider,model='test',local_disable_thinking=enabled))
            body=generation_request('write',settings,'system','user',{})
            assert body.get('reasoning_effort')==('none' if provider=='local' and enabled else None)


def test_evaluator_local_thinking():
    config=EvaluatorConfig(provider='local',model='test',max_input_chars=1000,local_disable_thinking=True)
    request=SimpleNamespace(messages=[],max_output_tokens=10,temperature=None,response_mode='prompt_json')
    assert evaluation_request(config,request)['reasoning_effort']=='none'


def test_false_flag_preserves_calibrated_evaluator_identity(monkeypatch):
    from storygen.evaluation.runner import evaluator_fingerprint
    from storygen.evaluation.prompting import load_rubric
    config=EvaluatorConfig(provider='local',model='test',max_input_chars=1000)
    current=evaluator_fingerprint(config,load_rubric())
    old_dump=EvaluatorConfig.model_dump
    def legacy_dump(self,*args,**kwargs):
        data=old_dump(self,*args,**kwargs);data.pop('local_disable_thinking',None);return data
    monkeypatch.setattr(EvaluatorConfig,'model_dump',legacy_dump)
    assert evaluator_fingerprint(config,load_rubric())==current
    monkeypatch.setattr(EvaluatorConfig,'model_dump',old_dump)
    config.local_disable_thinking=True
    assert evaluator_fingerprint(config,load_rubric())!=current
