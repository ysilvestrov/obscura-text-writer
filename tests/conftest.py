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
        dict(id="canon", version="1", kind="canon", text="Лєра має двадцять сім років. Вона фотографка."),
        dict(id="s1", version="1", kind="scene", text="Лєра відчинила двері студії. Їй було двадцять сім років."),
    ], target_ids=["s1"])


@pytest.fixture
def good_report():
    return JudgeReport(assessments=[dict(criterion_id=key, status="assessed", score=4, explanation="Проблем не виявлено.")
        for key in ["ukrainian", "style", "voice", "plan_fidelity"]], findings=[], checked_document_ids=["canon", "s1"], limitations=[])


@pytest.fixture
def calibrated_profile():
    return ScoringProfile(version="test-v1", calibrated=True, evaluator_fingerprint="test", calibration_fingerprint="test")
