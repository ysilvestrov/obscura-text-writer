"""All research self-checks are offline, including lifecycle/file tests."""
import socket

import pytest


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('Real network forbidden in research self-check')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
