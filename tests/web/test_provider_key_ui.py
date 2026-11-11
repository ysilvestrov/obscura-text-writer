import shutil
import subprocess
from pathlib import Path

import pytest

from storygen.web.localization import translate

ROOT = Path(__file__).resolve().parents[2]

TEXTS = {
    'keys.status.none': ('Ключ не задано.', 'No key set.'),
    'keys.status.store': ('Ключ збережено у сховищі Windows.', 'The key is saved in the Windows credential store.'),
    'keys.status.env': ('Ключ задано змінною середовища.', 'The key comes from an environment variable.'),
    'keys.status.env_and_store': ('Ключ задано змінною середовища; збережений у сховищі не використовується.',
                                  'The key comes from an environment variable; the saved one is not used.'),
    'keys.status.unavailable': ('Сховище ключів недоступне; задайте ключ змінною середовища.',
                                'The credential store is unavailable; set the key in an environment variable.'),
    'keys.save': ('Зберегти ключ', 'Save key'),
    'keys.delete': ('Видалити збережений ключ', 'Delete saved key'),
}


def test_status_keys_and_name_rules():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/provider_key.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('key', sorted(TEXTS))
def test_texts(key):
    assert (translate(key, 'uk'), translate(key, 'en')) == TEXTS[key]


def test_browser_name_rule_matches_the_server():
    from storygen.providers.secrets import _NAME
    source = (ROOT / 'src/storygen/web/static/provider-key.js').read_text(encoding='utf-8')
    assert f'/^{_NAME.pattern}$/' in source
