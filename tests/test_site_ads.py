"""DOCS-SITE-S11: Google tags of the site only after consent; the build adds the banner script only with `ads`."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.check_site import check, rehash
from tests.test_docs_site import make_site

ROOT=Path(__file__).resolve().parents[1]
ADS={'google_ads':'AW-1234567890','conversion_label':'AbC-12_x','ga4':'G-AB12CD34EF'}
GOOGLE=('googletagmanager','google-analytics','googleadservices','doubleclick','gtag(')


def site_with(tmp_path,ads=None,privacy=None):
    pages=None
    if privacy is not None:
        pages={'install':{'uk':'# Встановлення\n','en':'# Install\n'},'privacy':privacy}
    site=make_site(tmp_path,pages)
    shutil.copyfile(ROOT/'docs/site/consent.js',site/'consent.js')
    manifest=json.loads((site/'site.json').read_text(encoding='utf-8'))
    if ads is not None:manifest['ads']=ads
    (site/'site.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    for page in manifest['pages']:rehash(tmp_path,page['slug'])
    return site


@pytest.mark.req('DOCS-SITE')
def test_without_ads_the_site_has_no_banner_and_no_google(tmp_path):
    site_with(tmp_path);out=tmp_path/'out'
    build(tmp_path,out)
    for page in [out/'install.html',out/'en/install.html']:
        text=page.read_text(encoding='utf-8')
        assert 'consent.js' not in text and 'data-consent-open' not in text
        assert not any(name in text for name in GOOGLE)
        assert '{consent' not in text
    assert not (out/'consent.js').exists()


@pytest.mark.req('DOCS-SITE')
def test_with_ads_every_page_loads_the_banner_script_and_no_google_tag(tmp_path):
    site_with(tmp_path,ADS);out=tmp_path/'out'
    build(tmp_path,out)
    assert (out/'consent.js').read_text(encoding='utf-8')==(ROOT/'docs/site/consent.js').read_text(encoding='utf-8')
    for page,base,label in [(out/'install.html','','Налаштування cookies'),(out/'en/install.html','../','Cookie settings')]:
        text=page.read_text(encoding='utf-8')
        assert (f'<script src="{base}consent.js" defer data-ads="AW-1234567890" data-conversion="AbC-12_x" '
                'data-ga4="G-AB12CD34EF" data-privacy="privacy.html"></script>') in text
        assert f'<button type="button" class="site-consent-open" data-consent-open>{label}</button>' in text
        # The tag itself is added by consent.js only after Accept.
        assert not any(name in text for name in GOOGLE)


@pytest.mark.req('DOCS-SITE')
@pytest.mark.parametrize('field,value',[('google_ads','AW-abc'),('google_ads','G-1'),('conversion_label','a b'),
                                        ('conversion_label',''),('ga4','AW-1'),('ga4','G-ab"')])
def test_ads_ids_of_a_wrong_format_stop_the_build(tmp_path,field,value):
    site_with(tmp_path,{**ADS,field:value})
    with pytest.raises(ValueError,match='ads'):build(tmp_path,tmp_path/'out')


@pytest.mark.req('DOCS-SITE')
def test_ads_section_must_have_all_three_ids(tmp_path):
    site_with(tmp_path,{'google_ads':ADS['google_ads']})
    with pytest.raises(ValueError,match='ads'):build(tmp_path,tmp_path/'out')


PRIVACY_OK={'uk':'# Приватність\n\nCookies `_ga`, `_ga_<id>` і `_gcl_au`.\n','en':'# Privacy\n\nCookies `_ga`, `_ga_<id>` and `_gcl_au`.\n'}


@pytest.mark.req('DOCS-SITE')
def test_check_requires_privacy_to_name_google_cookies_when_ads_are_set(tmp_path):
    site_with(tmp_path,ADS,PRIVACY_OK)
    assert check(tmp_path)==[]


@pytest.mark.req('DOCS-SITE')
def test_check_fails_when_privacy_misses_google_cookies(tmp_path):
    site_with(tmp_path,ADS,{'uk':PRIVACY_OK['uk'],'en':'# Privacy\n\nNo cookies.\n'})
    errors=check(tmp_path)
    assert any('privacy' in e and 'en' in e and '_ga' in e for e in errors),errors


@pytest.mark.req('DOCS-SITE')
def test_check_fails_with_ads_and_no_privacy_page(tmp_path):
    site_with(tmp_path,ADS)
    assert any('privacy' in e for e in check(tmp_path))


@pytest.mark.req('DOCS-SITE')
def test_check_without_ads_does_not_require_google_cookies(tmp_path):
    site_with(tmp_path,None,{'uk':'# Приватність\n\nБез cookies.\n','en':'# Privacy\n\nNo cookies.\n'})
    assert check(tmp_path)==[]


@pytest.mark.req('DOCS-SITE')
def test_site_consent_script():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(ROOT/'tests/web/js/site_consent.mjs'),str(ROOT)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
