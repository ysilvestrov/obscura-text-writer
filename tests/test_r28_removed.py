"""R-44 PR 1: no code, page, prompt or catalog key of R-28 (impact check, review3/4) is left."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/storygen'
REMOVED_MODULES = re.compile(
    r'(?:from|import)\s+(?:\.+|storygen\.)(?:impact|review|generation\.impact_\w+|storage\.(?:impact|review)_\w+|'
    r'web\.routes_(?:impact|review)|token_budget\.local_\w+)\b'
    r'|from\s+\.+\s+import\s+(?:review_authority|review_store|impact_store)\b'
    r'|from\s+\.+(?:impact|review)\b')
REMOVED_ASSETS = ('review-session.js', 'impact.js', 'revision-page.js', 'revision-context.js', 'revision.html')


def test_no_r28_package_or_module_is_left():
    assert not (SRC / 'impact').exists() and not (SRC / 'review').exists()
    left = [p.relative_to(ROOT).as_posix() for p in SRC.rglob('*')
            if re.fullmatch(r'(impact_\w+|review_(store|authority|checks)|routes_(impact|review)|local_(counter|profiles|cli))\.py', p.name)
            or p.name in REMOVED_ASSETS or re.match(r'(impact_|review_part_)', p.name)]
    assert left == []


def test_no_import_or_reference_to_removed_code():
    found = []
    for path in SRC.rglob('*'):
        if path.suffix not in {'.py', '.js', '.html'}:
            continue
        text = path.read_text(encoding='utf-8')
        if path.suffix == '.py' and REMOVED_MODULES.search(text):
            found.append(path.relative_to(ROOT).as_posix())
        found += [f'{path.relative_to(ROOT).as_posix()}:{name}' for name in REMOVED_ASSETS if name in text]
    assert found == []


def test_catalog_has_no_r28_keys():
    catalog = json.loads((SRC / 'web/static/i18n.json').read_text(encoding='utf-8'))
    for locale in ('uk', 'en'):
        left = [k for k in catalog[locale] if k.startswith(('impact.', 'review.', 'review4.'))
                or k in {'workspace.menu_revision', 'workspace.review_attention', 'workspace.revision_pending',
                         'workspace.revision_return', 'plan_preamble.review'}]
        assert left == [], locale
