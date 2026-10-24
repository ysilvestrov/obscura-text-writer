import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_rename_story_preserves_materials_and_checks_revision(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Стара назва'}).json()
        scene=client.post(f'/api/stories/{story["id"]}/scenes',json={'title':'Сцена'}).json()
        repo=app.state.repo
        ref=repo.save_version(story['id'],scene['id'],'draft','Текст',[])
        before=repo.get_scene(scene['id']).model_dump()
        revision=repo.get_story(story['id']).revision
        url=f'/api/stories/{story["id"]}'
        response=client.patch(url,json={'title':'  Ніч <і> тіні  ','expected_revision':revision})
        assert response.status_code==200
        updated=response.json()
        assert updated['title']=='Ніч <і> тіні'
        assert updated['revision']==revision+1
        assert updated['config_revision']==story['config_revision']
        assert repo.get_scene(scene['id']).model_dump()==before
        assert repo.read_text(ref.id)=='Текст' and not repo.get_version(ref.id).stale
        assert 'Ніч &lt;і&gt; тіні' in client.get('/').text
        assert 'Ніч &lt;і&gt; тіні — Obscura' in client.get(f'/stories/{story["id"]}').text
        assert client.patch(url,json={'title':'Інша','expected_revision':revision}).status_code==409
        unchanged=client.patch(url,json={'title':updated['title'],'expected_revision':updated['revision']})
        assert unchanged.json()['revision']==updated['revision']
        for title in ['', '   ', 'x'*301]:
            assert client.patch(url,json={'title':title,'expected_revision':updated['revision']}).status_code in {400,422}
        removed=client.post(url+'/trash',json={'expected_revision':updated['revision']}).json()
        assert client.patch(url,json={'title':'Архів','expected_revision':removed['revision']}).status_code==404


def test_story_title_ui_preserves_input_and_scene_buffer():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(Path(__file__).parent/'js/story_title.mjs')],capture_output=True,encoding='utf8',timeout=15)
    assert result.returncode==0,result.stderr
