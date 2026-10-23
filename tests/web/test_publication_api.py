import io
from PIL import Image
from fastapi.testclient import TestClient
import pytest

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as c:
        yield c


def test_publication_page_fields_signature_crud_and_cas(client):
    story=client.post('/api/stories',json={'title':'Моя книга'}).json()
    base=f"/api/stories/{story['id']}/publication"
    view=client.get(base).json()
    assert view['effective_title']=='Моя книга' and view['card']['revision']==0
    author=client.post('/api/publication-signatures',json={'display_name':'Тінь'}).json()
    data={'title':'Публічна назва','author_ids':[author['id']],'keywords':['місто'],'publisher':'Видавець','rights':'Текст прав'}
    body={'expected_revision':0,'data':data,'expected_signature_revisions':{author['id']:0}}
    assert client.put(base,json=body).status_code==200
    assert client.put(base,json=body).status_code==409
    patch={'expected_revision':0,'display_name':'Інша тінь','archived':True}
    assert client.patch('/api/publication-signatures/'+author['id'],json=patch).status_code==200
    assert client.patch('/api/publication-signatures/'+author['id'],json=patch).status_code==409
    assert not client.get('/api/publication-signatures').json()['signatures']
    assert len(client.get('/api/publication-signatures?include_archived=true').json()['signatures'])==1
    assert client.get(base).json()['authors'][0]['display_name']=='Інша тінь'
    page=client.get(f"/stories/{story['id']}/publication")
    assert page.status_code==200 and 'publication.js' in page.text
    for field in ['title','annotation','language','genres','keywords','cycle_title','cycle_number','publication_date','publisher','isbn','rights','source_language']:
        assert f'name="{field}"' in page.text


def test_cover_http_bounds_owner_and_save(client):
    story=client.post('/api/stories',json={'title':'Книга'}).json()
    other=client.post('/api/stories',json={'title':'Інша'}).json()
    base=f"/api/stories/{story['id']}/publication"
    output=io.BytesIO(); Image.new('RGB',(12,18),'red').save(output,format='PNG')
    response=client.post(base+'/cover',files={'file':('../../escape.jpg',output.getvalue(),'text/plain')})
    assert response.status_code==200
    asset=response.json()
    assert client.get(base).json()['cover'] is None  # Upload does not silently save dirty form.
    url=base+'/covers/'+asset['id']
    downloaded=client.get(url)
    assert downloaded.status_code==200 and downloaded.headers['content-type']=='image/png'
    assert client.get(f"/api/stories/{other['id']}/publication/covers/{asset['id']}").status_code==404
    assert client.post(base+'/cover',files={'file':('cover.svg',b'<svg/>','image/svg+xml')}).status_code==400
    assert client.post(base+'/cover',files={'file':('big.png',b'x'*(10*1024*1024+1),'image/png')}).status_code==413
    assert client.put(base,json={'expected_revision':0,'expected_signature_revisions':{},'data':{'cover_id':asset['id']}}).status_code==200
    assert client.get(base).json()['cover']['id']==asset['id']


def test_publication_invalid_fields_and_archived_story(client):
    story=client.post('/api/stories',json={'title':'Книга'}).json()
    base=f"/api/stories/{story['id']}/publication"
    assert client.put(base,json={'expected_revision':0,'data':{'isbn':'wrong'},'expected_signature_revisions':{}}).status_code==422
    client.app.state.repo.set_story_trashed(story['id'],story['revision'],False)
    assert client.get(base).status_code==404
    assert client.get(f"/stories/{story['id']}/publication").status_code==404


def test_suggestion_http_readiness_history_and_atomic_save(tmp_path):
    from tests.generation.test_publication_metadata import seeded,run_proposal
    repo,story=seeded(tmp_path)
    run_proposal(repo,story)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as c:
        base=f'/api/stories/{story.id}/publication'
        assert c.get(base+'/suggestions/readiness').json()['ready']
        proposal=c.get(base+'/suggestions').json()['proposals'][0]
        body={'expected_revision':0,'data':{'annotation':'Після перегляду'},'suggestion':{
            'attempt_id':proposal['attempt_id'],'fingerprint':proposal['fingerprint'],'fields':['annotation']}}
        assert c.put(base,json=body).status_code==200
        body['expected_revision']=1
        assert c.put(base,json=body).status_code==409
        assert c.get(base).json()['card']['annotation']=='Після перегляду'
