"""CHARACTER-EXTRACT (R-51, spec §6): the characters page markup of the character search, its UI keys and the server
refusals it translates; the behaviour itself is in tests/web/browser/character-extract.spec.mjs."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate
from storygen.web.app import create_app

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT/'src/storygen/web/static'
CATALOG = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))


def characters_page(tmp_path) -> str:
    app = create_app(AppSettings(data_dir=tmp_path))
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        return client.get(f'/stories/{story.id}/characters').text


@pytest.mark.req('CHARACTER-EXTRACT')
def test_section_and_dialog_markup(tmp_path):
    html = characters_page(tmp_path)
    section = re.search(r'<section id="character-extract".*?</section>', html, re.S).group(0)
    assert re.search(r'<section id="character-extract"[^>]*\bhidden', section)  # shown once some scene has prose
    for id in ('character-extract-open', 'character-extract-run', 'character-extract-run-status', 'character-extract-pause',
               'character-extract-resume', 'character-extract-stop', 'character-proposal'):
        assert f'id="{id}"' in section, id
    assert 'aria-controls="character-extract-dialog"' in section
    start = html.index('<dialog id="character-extract-dialog"')
    dialog = html[start:html.index('</dialog>', start)]
    assert re.search(r'<input id="character-extract-words" type="number" min="1000" max="20000"[^>]*value="5000"', dialog)
    for id in ('character-extract-summary', 'character-extract-cost', 'character-extract-skipped', 'character-extract-pending',
               'character-extract-reason', 'character-extract-submit', 'character-extract-cancel'):
        assert f'id="{id}"' in dialog, id
    assert re.search(r'<p id="character-extract-status" role="status"', dialog)
    for key in set(re.findall(r'data-i18n="([^"]+)"', section + dialog)):
        assert key in CATALOG['uk'] and key in CATALOG['en'], key


@pytest.mark.req('CHARACTER-EXTRACT')
def test_ui_keys_exist_and_server_refusals_are_translated():
    script = (STATIC/'character-extract.js').read_text(encoding='utf-8')
    keys = set(re.findall(r"'(character_extract\.(?:ui|server)\.[a-z_]+)'", script))
    assert 'character_extract.ui.accept' in keys and 'character_extract.server.plan_changed' in keys
    for key in keys | {'memory_build.ui.find_characters'}:
        assert key in CATALOG['uk'] and key in CATALOG['en'], key
    # Every refusal and skip reason the search and the acceptance give is translated by its exact Ukrainian text.
    from storygen.characters import extract, extract_accept, extract_plan
    from storygen.generation import extract_context
    values = set(CATALOG['uk'].values())
    for module in (extract, extract_accept, extract_plan, extract_context):
        source = Path(module.__file__).read_text(encoding='utf-8')
        for name, value in vars(module).items():
            if name.isupper() and isinstance(value, str) and re.search('[а-яіїєґ]', value, re.I) and f'\n{name} = ' in source:
                assert value in values, (module.__name__, name)
    # The acceptance's inline refusals too (a "{what}: …" one by its pattern).
    from storygen.generation import worker
    source = Path(extract_accept.__file__).read_text(encoding='utf-8')
    for message in re.findall(r"raise ValueError\('([^']*[а-яіїєґ][^']*)'\)", source, re.I):
        assert message in values, message
    finished = 'Пошук персонажів завершено; запустіть новий'  # the worker's refusal to resume a finished search
    assert finished in Path(worker.__file__).read_text(encoding='utf-8') and finished in values
    assert "{p0}: ім'я не з пропозиції" in values
    assert "raise ValueError(f'{what}: ім\\'я не з пропозиції')" in (Path(extract_accept.__file__)).read_text(encoding='utf-8')


@pytest.mark.req('CHARACTER-EXTRACT')
def test_script_follows_the_cost_and_write_rules():
    script = (STATIC/'character-extract.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in script
    assert 'per_call_usd' not in script and 'total_usd' in script  # the total as the server gives it
    assert 'extract_plan_fingerprint:current.plan_fingerprint' in script
    assert script.count('/character-proposal/accept') == 2 and 'dry_run' in script
    assert "installCharacterExtract" in (STATIC/'characters.js').read_text(encoding='utf-8')
    assert "characters?extract=1" in (STATIC/'memory-build.js').read_text(encoding='utf-8')


@pytest.mark.req('CHARACTER-EXTRACT')
def test_selection_helpers():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT/'tests/web/js/character_extract.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    # Not-suggested names start unchosen; an unchosen card sends nothing; an update with no chosen names is dropped.
    assert data['default'] == {'cards': [{'key': 'n1', 'names': ['Марк']}],
                               'name_updates': [{'card_id': 'A', 'names': ['Оленка']}], 'protagonist': True, 'casts': ['s1']}
    assert data['without_card'] == {'cards': [], 'name_updates': [], 'protagonist': False, 'casts': []}
