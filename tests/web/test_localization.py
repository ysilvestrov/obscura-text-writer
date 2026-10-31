import json
from pathlib import Path
import subprocess
import pytest


def test_locale_selection_and_catalog():
    from storygen.web.localization import choose_locale, translate, catalogs
    assert choose_locale(None, 'en-US,en;q=0.8,uk;q=0.7') == 'en'
    assert choose_locale('uk', 'en-US') == 'uk'
    assert choose_locale('../../en', 'fr;q=1,en-GB;q=0.6') == 'en'
    assert choose_locale(None, 'en;q=0,uk;q=0') == 'uk'
    assert choose_locale(None, 'de,fr') == 'uk'
    assert translate('ui.save', 'en') == 'Save'
    assert translate('ui.save', 'uk') == 'Зберегти'
    assert set(catalogs()['uk']) == set(catalogs()['en'])


def test_live_locale_bindings():
    result=subprocess.run(['node',str(Path(__file__).parent/'js/localization.mjs')],capture_output=True,encoding='utf8',timeout=20)
    assert result.returncode == 0,result.stderr


def test_english_library_and_saved_override(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        page=client.get('/',headers={'accept-language':'en-US,en;q=0.9'}).text
        assert '<html lang="en"' in page
        assert 'Library' in page and 'data-ui-locale="en"' in page
        client.cookies.set('obscura_locale','uk')
        assert '<html lang="uk"' in client.get('/',headers={'accept-language':'en'}).text


def test_diagnostics_do_not_translate_author_parameters():
    from storygen.web.localization import diagnostic
    assert diagnostic('Матеріал не знайдено','en') == 'Material not found'
    assert diagnostic('Вкажіть публічний підпис','en') == 'Enter a public credit'
    assert diagnostic('Джерело <script>author</script>','en') == 'Джерело <script>author</script>'


def test_review_memory_guard_translates_only_its_message():
    from storygen.web.localization import diagnostic
    text='Пам’ять сцени «Авторська назва» містить авторські записи або вибір «передавати далі», які автоматична перебудова може втратити. Оновіть пам’ять цієї сцени вручну зі збереженням потрібних записів, потім відновіть перегляд.'
    translated=diagnostic(text,'en')
    assert translated.startswith('Memory for scene “Авторська назва”')
    assert 'Update that scene’s memory manually' in translated


def test_catalog_parameters_are_not_recursively_substituted():
    from storygen.web.localization import translate,catalogs
    import re
    for key,text in catalogs()['uk'].items():
        assert '__UNTRANSLATED__' not in catalogs()['en'][key]
        assert set(re.findall(r'{p\d+}',text)) == set(re.findall(r'{p\d+}',catalogs()['en'][key]))
    key=next(k for k,v in catalogs()['uk'].items() if v=='{p0}: {p1} · було: {p2}; тепер: {p3}')
    assert translate(key,'en',p0='{p1}',p1='<author>',p2='a',p3='b').startswith('{p1}: <author>')


def test_api_diagnostic_preserves_original(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        response=client.get('/api/stories/missing',headers={'accept-language':'en-US'})
        assert response.status_code==404
        assert response.json()['detail']=='Material not found'
        assert response.json()['detail_original']=='Матеріал не знайдено'
