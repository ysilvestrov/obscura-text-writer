import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


def test_allowed_levels_and_fallback():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/app_info.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name', ['rating-settings.js', 'scene-settings.js'])
def test_rating_forms_use_the_edition_limit(name):
    source = (STATIC / name).read_text(encoding='utf-8')
    assert "from './app-info.js'" in source and 'allowedLevels(' in source and "t('rating.edition.hint'" in source


def test_edition_hint_is_translated():
    from storygen.web.localization import translate
    assert translate('rating.edition.hint', 'uk', p0=1) == 'У цьому виданні Obscura найвищий рівень сексуального змісту — 1.'
    assert translate('rating.edition.hint', 'en', p0=1) == 'In this edition of Obscura the highest sexual content level is 1.'
