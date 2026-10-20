from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_brand_metadata_and_icon_are_served_for_every_surface(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path/'data')), base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories', json={'title':'Ніч <і> тіні','target_words':7000}).json()
        for path in ['/', f'/stories/{story["id"]}', f'/stories/{story["id"]}/settings']:
            page=client.get(path)
            assert page.status_code==200
            assert 'Obscura' in page.text
            assert 'name="application-name" content="Obscura"' in page.text
            assert 'rel="icon" type="image/svg+xml" href="/static/favicon.svg"' in page.text
        assert '<title>Obscura Text Writer</title>' in client.get('/').text
        assert '<title>Ніч &lt;і&gt; тіні — Obscura</title>' in client.get(f'/stories/{story["id"]}').text
        icon=client.get('/static/favicon.svg')
        assert icon.status_code==200
        assert icon.headers['content-type'].startswith('image/svg+xml')
        assert 'http://www.w3.org/2000/svg' in icon.text
