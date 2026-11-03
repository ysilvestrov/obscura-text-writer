"""Corpus-specific stage-one checks, separate from the stage-zero harness."""
import json
import hashlib
from pathlib import Path
import socket

import pytest

from .dataset import validate_dataset
from .requests import build_request


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('No network in corpus checks')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)


def test_authored_holdout():
    cases=json.loads(Path(__file__).with_name('holdout.json').read_text(encoding='utf-8'))
    assert validate_dataset(cases)['contradictions']==28
    for row in cases:
        req=build_request(row,dict(model='synthetic-local'))
        evidence=req['payload']['evidence']
        assert all(f'S{i+1}' in evidence for i in range(len(row['sources'])))
        for fact in row['gold']['contradictions']:
            assert any(fact['target_quote'] in e['text'] for e in evidence.values() if e['kind']=='target')


def test_approved_corpus_uses_git_newlines():
    path=Path(__file__).with_name('holdout.json');data=path.read_bytes()
    assert b'\r\n' not in data
    manifest=json.loads(path.with_name('manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(data).hexdigest()==manifest['holdout_sha256']


def test_author_draft_uses_lf(tmp_path,monkeypatch):
    from . import author_holdout
    monkeypatch.setattr(author_holdout,'__file__',str(tmp_path/'author_holdout.py'))
    author_holdout.main()
    assert b'\r\n' not in (tmp_path/'holdout.json').read_bytes()
    assert not (tmp_path/'holdout-review.md').read_bytes().endswith(b'\n\n')
