from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.memory.test_forwarding import seeded


def test_statistics_get_has_no_writes_or_dispatch(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    def snapshot():
        with repo.db.connection() as db:
            return {t:db.execute(f'SELECT * FROM {t}').fetchall() for t in ['stories','scenes','versions','stage_attempts','runs']}
    before=snapshot();calls=[]
    app=create_app(AppSettings(data_dir=tmp_path),gateway_factory=lambda p:calls.append(p))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        for stage in ['brief','draft','edit','memory']:
            response=client.get(f'/api/scenes/{scenes[1].id}/statistics?stage={stage}')
            assert response.status_code==200,response.text
            assert 'system_text' not in response.text and 'user_text' not in response.text
        assert client.get(f'/api/scenes/{scenes[1].id}/statistics?stage=unknown').status_code==422
    assert not calls and snapshot()==before
