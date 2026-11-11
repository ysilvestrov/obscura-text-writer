import json
import re
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.site_common import heading_id

ROOT=Path(__file__).resolve().parents[1]


def make_site(root,pages=None):
    """A minimal two-page, two-language site tree under root."""
    pages=pages or {
        'install':{'uk':'# Встановлення\n\n## Вимоги\n\nPython.\n\n## Вимоги\n\nЩе раз.\n','en':'# Install\n\n## Requirements\n\nPython.\n'},
        'first-story':{'uk':'# Перший твір\n\nДив. [вимоги](install.md#вимоги) і [сайт](https://example.com/a.md).\n','en':'# First story\n\nSee [requirements](install.md#requirements).\n'},
    }
    site=root/'docs/site'
    for lang in ['uk','en']:(site/lang).mkdir(parents=True,exist_ok=True)
    for slug,texts in pages.items():
        for lang,text in texts.items():(site/lang/f'{slug}.md').write_text(text,encoding='utf-8')
    manifest={'languages':['uk','en'],'pages':[{'slug':slug,'title':{'uk':slug,'en':slug}} for slug in pages]}
    (site/'site.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    for name in ['template.html','site.css']:(site/name).write_text((ROOT/'docs/site'/name).read_text(encoding='utf-8'),encoding='utf-8')
    (root/'docs/images/site').mkdir(parents=True,exist_ok=True)
    return site


@pytest.mark.req('DOCS-SITE')
def test_heading_ids_keep_cyrillic_and_number_repeats():
    seen={}
    assert heading_id('Вимоги',seen)=='вимоги'
    assert heading_id('Вимоги',seen)=='вимоги-2'
    assert heading_id('Вимоги',seen)=='вимоги-3'
    assert heading_id('Пам’ять і «сцени»!',seen)=='память-і-сцени'
    assert heading_id('Step 2: run `start.ps1`',seen)=='step-2-run-startps1'


@pytest.mark.req('DOCS-SITE')
def test_section_link_is_rewritten_and_target_has_id(tmp_path):
    make_site(tmp_path);out=tmp_path/'_site'
    build(tmp_path,out)
    page=(out/'first-story.html').read_text(encoding='utf-8')
    assert 'href="install.html#вимоги"' in page
    assert 'href="https://example.com/a.md"' in page  # external links are left alone
    install=(out/'install.html').read_text(encoding='utf-8')
    assert 'id="вимоги"' in install and 'id="вимоги-2"' in install


@pytest.mark.req('DOCS-SITE')
def test_build_is_relative_and_deterministic(tmp_path):
    make_site(tmp_path)
    build(tmp_path,tmp_path/'a');build(tmp_path,tmp_path/'b')
    files=sorted(p.relative_to(tmp_path/'a') for p in (tmp_path/'a').rglob('*') if p.is_file())
    assert Path('install.html') in files and Path('en/install.html') in files and Path('site.css') in files
    for rel in files:assert (tmp_path/'a'/rel).read_bytes()==(tmp_path/'b'/rel).read_bytes(),rel
    for rel in [p for p in files if p.suffix=='.html']:
        html=(tmp_path/'a'/rel).read_text(encoding='utf-8')
        for target in re.findall(r'(?:href|src)="([^"]+)"',html):
            if target.startswith(('http://','https://','mailto:')):continue
            assert not target.startswith('/'),(rel,target)
            path=target.split('#',1)[0]
            if path:assert ((tmp_path/'a'/rel).parent/path).resolve().is_file(),(rel,target)
    en=(tmp_path/'a/en/install.html').read_text(encoding='utf-8')
    assert '<html lang="en">' in en and 'href="../install.html"' in en and 'href="../site.css"' in en
    uk=(tmp_path/'a/install.html').read_text(encoding='utf-8')
    assert '<html lang="uk">' in uk and 'href="en/install.html"' in uk


def synced(root,**pages):
    from scripts.check_site import rehash
    site=make_site(root,**pages)
    for page in json.loads((site/'site.json').read_text(encoding='utf-8'))['pages']:rehash(root,page['slug'])
    return site


def site_errors(root):
    from scripts.check_site import check
    return check(root)


def test_synced_site_has_no_errors(tmp_path):
    synced(tmp_path)
    assert site_errors(tmp_path)==[]


@pytest.mark.req('DOCS-SITE')
@pytest.mark.parametrize('lang',['uk','en'])
def test_changed_one_language_fails_with_rehash_hint(tmp_path,lang):
    site=synced(tmp_path)
    page=site/lang/'install.md';page.write_text(page.read_text(encoding='utf-8')+'\nНовий рядок.\n',encoding='utf-8')
    errors=site_errors(tmp_path)
    assert len(errors)==1 and 'install' in errors[0] and f'docs/site/{lang}/install.md' in errors[0]
    assert 'python scripts/check_site.py --rehash install' in errors[0]


def test_line_endings_alone_do_not_need_rehash(tmp_path):
    site=synced(tmp_path)
    page=site/'uk/install.md';data=page.read_bytes()
    page.write_bytes(data.replace(b'\r\n',b'\n') if b'\r\n' in data else data.replace(b'\n',b'\r\n'))
    assert site_errors(tmp_path)==[]


@pytest.mark.req('DOCS-SITE')
@pytest.mark.parametrize('target',['../../superpowers/plans/x.md','../../research/a.md','../../diagnostics/a.md','../../specs/a.md','../../../SPEC.MD','../../STATUS.md#стан'])
def test_internal_material_link_fails(tmp_path,target):
    site=make_site(tmp_path)
    (site/'uk/install.md').write_text(f'# Встановлення\n\n## Вимоги\n\n[план]({target})\n',encoding='utf-8')
    from scripts.check_site import rehash
    for slug in ['install','first-story']:rehash(tmp_path,slug)
    errors=site_errors(tmp_path)
    assert any('внутрішн' in e and 'docs/site/uk/install.md:5' in e for e in errors),errors


@pytest.mark.req('DOCS-SITE')
def test_missing_anchor_fails(tmp_path):
    site=synced(tmp_path)
    (site/'en/first-story.md').write_text('# First story\n\nSee [x](install.md#no-such-part).\n',encoding='utf-8')
    from scripts.check_site import rehash
    rehash(tmp_path,'first-story')
    errors=site_errors(tmp_path)
    assert any('install.md#no-such-part' in e and 'docs/site/en/first-story.md:3' in e for e in errors),errors


def test_missing_pair_image_alt_and_outside_md(tmp_path):
    site=synced(tmp_path)
    (site/'en/install.md').unlink()
    (tmp_path/'docs/images/site/uk').mkdir(parents=True)
    (tmp_path/'docs/images/site/uk/a.png').write_bytes(b'png')
    (site/'uk/first-story.md').write_text('# Перший твір\n\n![](../../images/site/uk/a.png)\n\n![Знімок](../../images/site/uk/none.png)\n\n[README](../../../README.md)\n',encoding='utf-8')
    errors='\n'.join(site_errors(tmp_path))
    assert 'docs/site/en/install.md' in errors and 'немає' in errors
    assert 'docs/site/uk/first-story.md:3' in errors and 'alt' in errors
    assert 'none.png' in errors
    assert 'README.md' in errors


def test_rehash_records_both_hashes(tmp_path):
    synced(tmp_path)
    data=json.loads((tmp_path/'docs/site/sync.json').read_text(encoding='utf-8'))
    assert set(data)=={'install','first-story'} and all(set(v)=={'uk','en'} and len(v['uk'])==64 for v in data.values())


def test_check_docs_includes_site_errors(tmp_path,monkeypatch):
    import scripts.check_docs as check_docs
    site=synced(tmp_path)
    (site/'uk/install.md').write_text('# змінено\n',encoding='utf-8')
    monkeypatch.setattr(check_docs,'spec_index',lambda text:({},{},[]))
    (tmp_path/'SPEC.MD').write_text('',encoding='utf-8');(tmp_path/'docs/verification').mkdir(parents=True)
    (tmp_path/'docs/verification/traceability.json').write_text('{"version":1,"scenarios":[]}',encoding='utf-8')
    errors=check_docs.check(tmp_path,documents=[])
    assert any('--rehash install' in e for e in errors),errors


def workflow_jobs(text):
    """Split the workflow into top-level job blocks by two-space-indented keys under `jobs:`."""
    body=text.split('\njobs:\n',1)[1];jobs={};name=None
    for line in body.splitlines():
        match=re.match(r'^  ([A-Za-z0-9_-]+):\s*$',line)
        if match:name=match[1];jobs[name]=[]
        elif name:jobs[name].append(line)
    return {key:'\n'.join(value) for key,value in jobs.items()},text.split('\njobs:\n',1)[0]


@pytest.mark.req('DOCS-SITE')
def test_workflow_publishes_only_from_main():
    text=(ROOT/'.github/workflows/site.yml').read_text(encoding='utf-8')
    jobs,head=workflow_jobs(text)
    assert 'pull_request:' in head and 'push:' in head and 'branches: [main]' in head
    assert re.search(r'^permissions:\n  contents: read\n(?!  )',head,re.M),head
    assert 'pages: write' not in head and 'id-token: write' not in head
    deploy=[name for name,block in jobs.items() if 'actions/deploy-pages@' in block]
    assert deploy==['deploy'],deploy
    block=jobs['deploy']
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in block
    assert 'group: pages' in block and 'cancel-in-progress: false' in block
    assert 'pages: write' in block and 'id-token: write' in block
    assert 'curl --fail' in block
    for name,job in jobs.items():
        if name!='deploy':assert 'pages: write' not in job and 'upload-pages-artifact' not in job,name
    assert 'scripts/build_site.py' in jobs['build'] and 'scripts/check_site.py' in jobs['build']


@pytest.mark.req('DOCS-SITE')
def test_heading_suffix_collision_gets_a_fresh_id():
    seen={}
    assert [heading_id(t,seen) for t in ['A','A-2','A']]==['a','a-2','a-3']


@pytest.mark.req('DOCS-SITE')
@pytest.mark.parametrize('body,needle',[
    ('[тут][x]\n\n[x]: missing.md\n','missing.md'),
    ('![][img]\n\n[img]: ../../images/site/uk/none.png\n','none.png'),
    ('![](https://example.com/shot.png)\n','https://example.com/shot.png'),
])
def test_reference_links_and_external_images_are_checked(tmp_path,body,needle):
    site=synced(tmp_path)
    (site/'uk/first-story.md').write_text('# Перший твір\n\n'+body,encoding='utf-8')
    from scripts.check_site import rehash
    rehash(tmp_path,'first-story')
    assert any(needle in e for e in site_errors(tmp_path)),site_errors(tmp_path)


@pytest.mark.req('DOCS-SITE')
def test_dot_slash_page_link_is_rewritten(tmp_path):
    site=synced(tmp_path)
    (site/'uk/first-story.md').write_text('# Перший твір\n\n[встановлення](./install.md#вимоги)\n',encoding='utf-8')
    from scripts.check_site import rehash
    rehash(tmp_path,'first-story')
    assert site_errors(tmp_path)==[]
    build(tmp_path,tmp_path/'_site')
    assert 'href="install.html#вимоги"' in (tmp_path/'_site/first-story.html').read_text(encoding='utf-8')


@pytest.mark.req('DOCS-SITE')
def test_deploy_skips_a_commit_that_is_no_longer_main():
    jobs,head=workflow_jobs((ROOT/'.github/workflows/site.yml').read_text(encoding='utf-8'))
    block=jobs['deploy']
    assert 'git ls-remote' in block and 'refs/heads/main' in block and 'GITHUB_SHA' in block
    assert block.index('git ls-remote')<block.index('actions/deploy-pages@')


@pytest.mark.req('DOCS-SITE')
def test_reference_link_to_internal_material_and_raw_html_are_not_published(tmp_path):
    site=synced(tmp_path)
    (site/'uk/first-story.md').write_text('# Перший твір\n\n[план\nдалі][r]\n\n[r]: ../../../SPEC.MD\n\n<a href="../../superpowers/x.md">x</a>\n',encoding='utf-8')
    from scripts.check_site import rehash
    rehash(tmp_path,'first-story')
    assert any('внутрішній' in e and 'SPEC.MD' in e for e in site_errors(tmp_path)),site_errors(tmp_path)
    build(tmp_path,tmp_path/'_site')
    assert '<a href="../../superpowers' not in (tmp_path/'_site/first-story.html').read_text(encoding='utf-8')


@pytest.mark.req('DOCS-SITE')
def test_heading_id_uses_visible_text_only(tmp_path):
    make_site(tmp_path,{'install':{'uk':'# Розділ з `code` і [лінком](first-story.md)\n','en':'# Install\n'},'first-story':{'uk':'# A\n','en':'# A\n'}})
    build(tmp_path,tmp_path/'_site')
    assert 'id="розділ-з-code-і-лінком"' in (tmp_path/'_site/install.html').read_text(encoding='utf-8')
