import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.authoring.test_ebook_exports import seeded


@pytest.mark.parametrize('format,mime',[('fb2','application/x-fictionbook+xml'),('epub','application/epub+zip'),('pdf','application/pdf')])
def test_ebook_api_download_headers_integrity_and_ownership(tmp_path,format,mime):
    repo,story=seeded(tmp_path,count=1)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        response=client.post(f'/api/stories/{story.id}/export',json={'format':format})
        assert response.status_code==200,response.text
        urls=response.json();download=client.get(urls['download_url'])
        assert download.status_code==200 and download.headers['content-type'].startswith(mime)
        assert 'attachment' in download.headers['content-disposition']
        assert client.get(urls['manifest_url']).json()['schema_version']==2
        other=client.post('/api/stories',json={'title':'Інший'}).json()
        assert client.get(urls['download_url'].replace(story.id,other['id'])).status_code==404
        name=urls['download_url'].rsplit('/',1)[-1]
        repo.files.resolve(f'stories/{story.id}/exports/{name}').write_bytes(b'broken')
        assert client.get(urls['download_url']).status_code==409
        assert client.get(urls['manifest_url']).status_code==409
