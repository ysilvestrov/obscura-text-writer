import copy
import shutil
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def payload(scene_id=None,text='Авторський факт'):
    return [{'id':None,'name':'Анна','entries':[{'id':None,'text':text,'origin':'author','sources':[],
        'availability':'from_scene' if scene_id else 'unclassified','available_from_scene_id':scene_id}]}]


def test_author_api_preview_and_save_are_separate_and_ids_are_stable(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Мітки'}).json()
        first=client.post(f"/api/stories/{story['id']}/scenes",json={'title':'Перша'}).json()
        later=client.post(f"/api/stories/{story['id']}/scenes",json={'title':'Пізня'}).json()
        url=f"/api/stories/{story['id']}/characters"
        loaded=client.get(url)
        assert loaded.status_code==200
        data=loaded.json();cards=payload(later['id'],'Майбутній факт')
        preview=client.post(url+'/preview',json={'cards':cards,'scene_id':first['id']})
        assert preview.status_code==200 and 'Майбутній факт' not in preview.json()['text']
        assert client.get(url).json()['version_id'] is None
        saved=client.put(url,json={'expected_revision':data['revision'],'cards':cards})
        assert saved.status_code==200,saved.text
        actual=saved.json();old_id=actual['cards'][0]['entries'][0]['id']
        cards=copy.deepcopy(actual['cards']);cards[0]['entries'][0]['text']='Уточнений факт'
        changed=client.put(url,json={'expected_revision':actual['revision'],'cards':cards})
        assert changed.status_code==200 and changed.json()['cards'][0]['entries'][0]['id']==old_id
        assert client.put(url,json={'expected_revision':actual['revision'],'cards':cards}).status_code==409


def test_character_api_rejects_wrong_anchor_quote_owner_and_duplicate_ids(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Перевірки'}).json();url=f"/api/stories/{story['id']}/characters"
        scene=client.post(f"/api/stories/{story['id']}/scenes",json={'title':'Сцена'}).json()
        revision=client.get(url).json()['revision']
        assert client.put(url,json={'expected_revision':revision,'cards':payload('missing')}).status_code==400
        source=app.state.repo.save_version(story['id'],None,'source_characters','Дослівний опис',[])
        cards=payload();entry=cards[0]['entries'][0];entry.update(origin='imported',sources=[{'version_id':source.id,'quote':'Вигадана цитата'}])
        assert client.put(url,json={'expected_revision':revision,'cards':cards}).status_code==400
        entry['sources'][0]['quote']='Дослівний опис'
        result=client.put(url,json={'expected_revision':revision,'cards':cards})
        assert result.status_code==200,result.text
        actual=result.json();duplicates=actual['cards']*2
        assert client.put(url,json={'expected_revision':actual['revision'],'cards':duplicates}).status_code==400
        foreign=client.post('/api/stories',json={'title':'Інший'}).json()
        other=app.state.repo.save_version(foreign['id'],None,'source_characters','Дослівний опис',[])
        cards=payload();cards[0]['entries'][0].update(origin='imported',sources=[{'version_id':other.id,'quote':'Дослівний опис'}])
        assert client.put(url,json={'expected_revision':actual['revision'],'cards':cards}).status_code==400


def test_character_buffer_preserves_new_edits_and_rejects_stale_preview():
    node=shutil.which('node')
    if not node:return
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/character_editor.mjs'),str(root)],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stderr
