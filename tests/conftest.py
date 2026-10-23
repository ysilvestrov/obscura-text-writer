import socket
import threading

import pytest

from storygen.evaluation.models import EvaluationCase, JudgeReport, ScoringProfile


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    local=threading.local()
    socketpair=socket.socketpair
    def internal_pair(*args,**kwargs):
        local.in_pair=True
        try:
            return socketpair(*args,**kwargs)
        finally:
            local.in_pair=False
    def guard(original):
        def checked(*args,**kwargs):
            if getattr(local,"in_pair",False):
                return original(*args,**kwargs)
            raise AssertionError("Тест не повинен звертатися до мережі")
        return checked
    monkeypatch.setattr(socket,"socketpair",internal_pair)
    monkeypatch.setattr(socket.socket,"connect",guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket,"connect_ex",guard(socket.socket.connect_ex))


@pytest.fixture
def sample_case():
    return EvaluationCase(id="sample", mode="scene", documents=[
        dict(id="canon", version="1", kind="canon", text="Олена має сорок років. Вона бібліотекарка."),
        dict(id="s1", version="1", kind="scene", text="Олена відчинила двері бібліотеки. Їй було сорок років."),
    ], target_ids=["s1"])


@pytest.fixture
def accounted_call(tmp_path):
    """Real isolated ledger for mocked cloud transports; never a budget bypass."""
    from datetime import timedelta
    from uuid import uuid4
    from storygen.storage.repository import Repository
    from storygen.billing.models import Tariff, utcnow
    from storygen.billing.service import set_limit, save_tariff
    from storygen.providers.accounting import CallAccounting
    repo=Repository(tmp_path/'accounting')
    set_limit(repo,'cli:mock','1000',0)
    def create(provider,model):
        endpoint={'venice':'https://api.venice.ai/api/v1','openrouter':'https://openrouter.ai/api/v1'}[provider]
        save_tariff(repo,Tariff(provider=provider,model=model,base_url=endpoint,input_per_million='1',output_per_million='2',
            source='mock provider tariff',kind='manual',expires_at=(utcnow()+timedelta(days=1)).isoformat()))
        return CallAccounting(repo,'cli:mock','mock-run',uuid4().hex)
    return create


@pytest.fixture
def good_report():
    return JudgeReport(assessments=[dict(criterion_id=key, status="assessed", score=4, explanation="Проблем не виявлено.")
        for key in ["ukrainian", "style", "voice", "plan_fidelity"]], findings=[], checked_document_ids=["canon", "s1"], limitations=[])


@pytest.fixture
def calibrated_profile():
    return ScoringProfile(version="test-v1", calibrated=True, evaluator_fingerprint="test", calibration_fingerprint="test")
