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
    for id in ['run-status','run-actions','workspace-error-settings','run-options','workspace-scene-status']:
        assert id in tree.ancestors,id
        assert '#workspace-status-row' in tree.ancestors[id],id
    assert '.workspace-sticky' not in tree.ancestors['review-attention']
    assert '#workspace' in tree.ancestors['review-attention']
    assert 'workspace-status"' not in html.split('class="context-panel"')[1]


@pytest.mark.req('R20-WORKSPACE')
def test_pinned_area_keeps_only_tabs_toolbar_and_notes(tmp_path):
    tree,html=page(tmp_path)
    # Status row, run controls and the waiting review card scroll with the page under the material.
    for id in ['workspace-status-row','review-attention','workspace-hint-info']:
        assert '.workspace-sticky' not in tree.ancestors[id],id
    material=html.index('id="workspace-material"')
    assert material<html.index('id="workspace-hint-info"')<html.index('id="workspace-status-row"')<html.index('id="review-attention"')
    assert tree.attrs['review-attention'].get('tabindex')=='-1'
    # What must stay in view while typing: the blocked-action reason, the external origin and change notices.
    for id in ['workspace-hint','workspace-origin','external-change']:
        assert {'.workspace-sticky','.workspace-pinned-notes'}<=tree.ancestors[id],id
    for id in ['run-jump','workspace-focus']:
        assert {'.workspace-sticky','.editor-toolbar'}<=tree.ancestors[id],id
    assert 'hidden' in tree.attrs['run-jump'] and tree.attrs['run-jump'].get('href')=='#workspace-status-row'
    focus=tree.attrs['workspace-focus']
    assert focus.get('aria-pressed')=='false' and focus.get('aria-label') and focus.get('title')


@pytest.mark.req('WORKSPACE-TOOLS')
def test_story_toolbar_has_three_icon_actions_and_a_disclosure_menu(tmp_path):
    tree,html=page(tmp_path)
    toggle=tree.attrs['story-menu-toggle']
    assert toggle.get('aria-expanded')=='false' and toggle.get('aria-controls')=='story-menu'
    for id in ['workspace-characters','workspace-settings','add-scene']:
        assert tree.attrs[id].get('aria-label') and tree.attrs[id].get('title'),id
        assert '.storybar' in tree.ancestors[id],id
    for id in ['story-menu-revision','story-menu-publication','export-story','story-menu-evaluate','story-menu-reports','story-menu-budget','story-menu-rename']:
        assert '#story-menu' in tree.ancestors[id],id
    assert '#export-dialog' in tree.ancestors['export-form']
    assert tree.attrs['story-menu-budget']['href'].endswith('/settings?section=budget')  # settingsRoute reads ?section= only
    for id in ['impact-panel','impact-reports','impact-preview']:
        assert id not in tree.attrs,id
    assert '#review-attention' in tree.ancestors['review-session']
    assert 'class="context-panel"' in html and 'publication-panel' not in html


@pytest.mark.req('IMPACT-UI')
def test_book_revision_page_hosts_impact_review(tmp_path):
    tree,html=page(tmp_path,'/stories/{id}/revision')
    for id in ['impact-panel','impact-preview','impact-reports','review-session','revision-return']:
        assert id in tree.attrs,id
    assert '"/static/editor.js": "/static/revision-context.js"' in html


@pytest.mark.req('WORKSPACE-TOOLS')
def test_side_panel_holds_only_scene_sections(tmp_path):
    tree,html=page(tmp_path)
    panel=html.split('class="context-panel"')[1].split('</aside>')[0]
    assert panel.count('class="tool-section"')==2
    assert 'data-section="scene"' in panel and 'data-section="evaluation"' in panel
    assert {'.context-panel','.tool-section'}<=tree.ancestors['context-content']
    assert {'.context-panel','#evaluation-section'}<=tree.ancestors['evaluation-panel']
    assert '.importer' in tree.ancestors['import-journal']
    assert 'm_67b44565c06d' not in panel
