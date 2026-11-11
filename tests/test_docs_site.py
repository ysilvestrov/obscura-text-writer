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
