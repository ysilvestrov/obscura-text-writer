from pathlib import Path
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.server import main


def test_installed_package_finds_templates_outside_repo(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(AppSettings(data_dir=tmp_path/'data')),base_url='http://127.0.0.1:8765') as client:
        assert 'Історії починаються тут' in client.get('/').text
        assert client.get('/static/runs.js').status_code==200


def test_server_help_does_not_start_models(capsys):
    import pytest
    with pytest.raises(SystemExit) as exc:main(['--help'])
    assert exc.value.code==0
    assert '--data-dir' in capsys.readouterr().out


def test_browser_documents_and_imported_modules_are_not_cached(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path/'data')),base_url='http://127.0.0.1:8765') as client:
        for path in ['/', '/static/versions.js', '/static/editor.js', '/static/api.js', '/static/app.css']:
            response=client.get(path)
            assert response.status_code==200
            assert response.headers.get('cache-control')=='no-store',path
        script=client.get('/static/versions.js')
        conditional=client.get('/static/versions.js',headers={'If-None-Match':script.headers['etag']})
        assert conditional.status_code in {200,304}
        assert conditional.headers.get('cache-control')=='no-store'
