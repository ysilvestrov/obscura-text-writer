import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_book_validation_helpers():
    """R-44 book validation: menu counter, preview text with the upper bound, stopped run → its scene."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/book_validation.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_book_validation_texts_exist_in_both_languages():
    catalogs = json.loads((ROOT / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))
    keys = ['book_validation.menu', 'book_validation.menu_count', 'book_validation.valid', 'book_validation.accept',
            'book_validation.review_again', 'audit.confirm_scenes', 'audit.confirm_calls', 'audit.cost_total',
            'audit.cost_unknown', 'audit.book_bound', 'audit.confirm_start', 'run.mode_audit_book', 'run.go_to_scene', 'run.on_stop_scene', 'book_validation.finish']
    for locale in ('uk', 'en'):
        missing = [key for key in keys if not catalogs[locale].get(key)]
        assert missing == [], (locale, missing)
