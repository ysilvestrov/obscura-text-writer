"""#89: the scene/story boundary of the workspace, read from the rendered page."""
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


class Tree(HTMLParser):
    """Records, for each element id, the ids and classes of its ancestors."""
    def __init__(self):
        super().__init__();self.stack=[];self.ancestors={};self.attrs={}
    VOID={'input','br','img','meta','link','hr','source','path','circle','line','rect','polyline'}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);marks={'#'+a['id']} if a.get('id') else set()
        marks|={'.'+c for c in (a.get('class') or '').split()}
        if a.get('id'):self.ancestors[a['id']]=set().union(*self.stack) if self.stack else set();self.attrs[a['id']]=a
        if tag not in self.VOID:self.stack.append(marks)
    def handle_endtag(self,tag):
        if tag not in self.VOID and self.stack:self.stack.pop()


def page(tmp_path,path='/stories/{id}'):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Pier lighthouse'}).json()
        response=client.get(path.format(id=story['id']));assert response.status_code==200
    tree=Tree();tree.feed(response.text);return tree,response.text


@pytest.mark.req('R20-WORKSPACE')
def test_run_controls_and_limit_live_in_the_status_row(tmp_path):
    tree,html=page(tmp_path)
    for id in ['run-status','run-actions','workspace-error-settings','run-options','review-attention','workspace-scene-status']:
        assert id in tree.ancestors,id
        assert {'.workspace-sticky','#workspace-status-row'}<=tree.ancestors[id],id
    assert 'workspace-status"' not in html.split('class="context-panel"')[1]
