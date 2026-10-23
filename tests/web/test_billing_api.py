from fastapi.testclient import TestClient
from storygen.web.app import create_app
from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate


def test_budget_revision_and_no_default_money(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    story=app.state.repo.create_story(StoryCreate(title='Облік'))
    with TestClient(app,base_url='http://127.0.0.1') as client:
        url=f'/api/stories/{story.id}/budget'
        response=client.get(url)
        assert response.status_code==200
        assert response.json()['limit_nanos'] is None
        result=client.put(url,json={'limit_usd':'1.00','expected_revision':0})
        assert result.status_code==200 and result.json()['limit_nanos']==10**9
        assert client.put(url,json={'limit_usd':'2','expected_revision':0}).status_code==409
        assert client.get(url+'/calls').json()==[]


def test_manual_tariff_requires_source_and_future_date(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    story=app.state.repo.create_story(StoryCreate(title='Облік'))
    with TestClient(app,base_url='http://127.0.0.1') as client:
        url=f'/api/stories/{story.id}/budget/prices'
        result=client.post(url,json={'provider':'venice','model':'m','input_per_million':'1','output_per_million':'2',
            'source':'','expires_at':'2020-01-01T00:00:00+00:00'})
        assert result.status_code in {400,422}
