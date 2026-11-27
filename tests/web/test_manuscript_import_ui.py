"""MANUSCRIPT-IMPORT UI: the library entry point and the import dialog, read from the rendered library and the static files."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app

STATIC = Path(__file__).resolve().parents[2]/'src/storygen/web/static'


def library(tmp_path) -> str:
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        return client.get('/').text


def dialog_of(html: str) -> str:
    start = html.index('<dialog id="manuscript-import-dialog"')
    return html[start:html.index('</dialog>', start)]


def test_library_has_the_import_entry_and_dialog(tmp_path):
    html = library(tmp_path)
    form_end = html.index('</form>', html.index('<form id="new-story"'))
    entry = re.search(r'<button[^>]*\bid="manuscript-import-open"[^>]*>', html)
    assert entry and form_end < entry.start() < form_end + 400  # next to the new-book form
    assert 'aria-haspopup="dialog"' in entry.group(0) and 'aria-controls="manuscript-import-dialog"' in entry.group(0)
    dialog = dialog_of(html)
    assert re.search(r'class="export-dialog manuscript-import-dialog"', dialog[:200])
    assert 'aria-labelledby="manuscript-import-title"' in dialog[:200]
    assert re.search(r'<input[^>]*id="manuscript-import-file"[^>]*type="file"[^>]*accept="\.docx,\.md,\.txt"', dialog)
    assert re.search(r'<p id="manuscript-import-status" role="status"', dialog)
    assert re.search(r'<input[^>]*id="manuscript-import-book-title"[^>]*maxlength="300"', dialog)
    for id in ('manuscript-import-pick', 'manuscript-import-preview', 'manuscript-import-result', 'manuscript-import-scenes',
               'manuscript-import-language', 'manuscript-import-chapter-markers', 'manuscript-import-part-markers',
               'manuscript-import-series-warning',
               'manuscript-import-chapter-source', 'manuscript-import-front-matter', 'manuscript-import-warnings',
               'manuscript-import-submit', 'manuscript-import-cancel', 'manuscript-import-series', 'manuscript-import-series-number'):
        assert f'id="{id}"' in dialog, id
    for axis in ('sexual', 'violence', 'themes'):
        assert f'id="manuscript-import-rating-{axis}"' in dialog
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    keys = set(re.findall(r'data-i18n="([^"]+)"', dialog + entry.group(0) + html[entry.end():entry.end() + 300]))
    assert 'manuscript_import.ui.open' in keys and 'manuscript_import.ui.title' in keys
    for key in keys:
        assert key in catalog['uk'] and key in catalog['en'], key
    assert 'import {installManuscriptImport} from "/static/manuscript-import.js"' in html


def test_series_fields_follow_the_trial_in_store(tmp_path, store_edition):
    """LONG-PROSE-TRIAL-S07: rows render while the trial is free (the dialog hides them by state); a trial on a book
    removes them. The import itself is in every edition."""
    from storygen.domain import StoryCreate
    from storygen.storage.long_prose_trial import claim_target
    from datetime import datetime, timezone
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        free = client.get('/').text
        repo = client.app.state.repo
        story = repo.create_story(StoryCreate(title='Книга'))
        claim_target(repo, story_id=story.id, series_id=None, now=datetime(2026, 11, 27, tzinfo=timezone.utc))
        used = client.get('/').text
    assert 'id="manuscript-import-open"' in free and 'id="manuscript-import-open"' in used
    assert 'id="manuscript-import-series"' in dialog_of(free) and 'id="manuscript-import-part-markers"' in dialog_of(free)
    dialog = dialog_of(used)
    assert 'id="manuscript-import-series"' not in dialog and 'id="manuscript-import-series-number"' not in dialog
    assert 'id="manuscript-import-part-markers"' not in dialog


def test_template_wraps_the_series_row_in_the_series_screen_gate():
    template = (Path(__file__).resolve().parents[2]/'src/storygen/web/templates/library.html').read_text(encoding='utf-8')
    for id in ('manuscript-import-series-row', 'manuscript-import-series-warning', 'manuscript-import-part-markers-row'):
        row = template.index(f'id="{id}"')
        opened = template.rfind('{% if series_screen() %}', 0, row)
        assert opened != -1 and template.find('{% endif %}', opened) > row, id


def test_strings_and_limits():
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    assert catalog['uk']['manuscript_import.ui.open'] == 'Імпорт рукопису (DOCX, Markdown, TXT)…'
    assert catalog['uk']['manuscript_import.ui.front_matter'] == 'Додати передмову на початок першої сцени'
    assert catalog['uk']['manuscript_import.ui.boundary_add'] == 'Межа тут'
    assert catalog['uk']['manuscript_import.ui.boundary_remove'] == 'Прибрати межу'
    assert catalog['uk']['manuscript_import.ui.build_memory'] == 'Побудувати пам’ять (сцен: {p0})'
    assert catalog['en']['manuscript_import.ui.build_memory'] == 'Build memory (scenes: {p0})'
    ui = {key for key in catalog['uk'] if key.startswith('manuscript_import.ui.')}
    assert ui == {key for key in catalog['en'] if key.startswith('manuscript_import.ui.')}
    script = (STATIC/'manuscript-import.js').read_text(encoding='utf-8')
    # Server texts (warnings, errors) arrive in Ukrainian; every one passes through diagnostic().
    assert 'diagnostic(' in script and "method:'DELETE'" in script
    assert 'MAX_FILE=20*1024*1024' in script and 'MAX_SCENES=500' in script and 'MAX_PARAGRAPHS=2000' in script
    assert '?build_memory=1' in script
    for key in re.findall(r"t\('(manuscript_import\.ui\.[a-z_.]+)'", script):
        assert key in catalog['uk'] and key in catalog['en'], key


def test_js_boundary_logic():
    import subprocess
    result = subprocess.run(['node', str(Path(__file__).parent/'js'/'manuscript_import_boundaries.mjs')],
                            capture_output=True, encoding='utf8', timeout=20)
    assert result.returncode == 0, result.stderr
