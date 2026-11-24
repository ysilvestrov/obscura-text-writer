import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.req('VALID-LINKS')
@pytest.mark.req('VALID-MEMORY')
def test_link_panel_actions():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/link_decision.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_material_status_carries_the_auditor_verdict_of_the_current_link(tmp_path):
    """The discrepancy panel reads the latest auditor verdict from the story view: confidence, items and summary."""
    from storygen.generation.audit import audit_link
    from storygen.storage.material_status import material_status
    from tests.generation.test_audit_verdict import AuditGateway, answer, unchecked_scene
    from tests.storage.test_links import run_for
    repo, story, (scene,) = unchecked_scene(tmp_path)
    items = [{'text': 'Місце не збігається', 'quote': 'У студії тихо.'}, {'text': 'Немає кроку', 'quote': None}]
    result = audit_link(repo, scene.id, 'brief', AuditGateway(answer(40, items, 'Можлива розбіжність')),
                        run_id=run_for(repo, story, scene, 'audit-' + scene.id))
    assert result.outcome == 'discrepancy'
    links = material_status(repo.context_view(story.id))[scene.id]['links']
    assert links['brief']['status'] == 'discrepancy' and links['brief']['source'] == 'auditor'
    assert links['brief']['confidence'] == 40
    assert links['brief']['discrepancies'] == items
    assert links['brief']['summary'] == 'Можлива розбіжність'
    # A link without an auditor verdict keeps the plain shape.
    assert set(links['prose']) == {'status', 'source', 'reason', 'fingerprint'}


CONSISTENCY_KEYS = ['consistency.approve_self', 'consistency.audit', 'consistency.audit_calls', 'consistency.audit_cost', 'consistency.discrepancy_hint', 'consistency.no_discrepancy', 'consistency.nothing_to_audit', 'consistency.pending_count', 'consistency.resolve_first', 'consistency.resume', 'consistency.row_brief', 'consistency.row_memory', 'consistency.row_prose', 'consistency.state_discrepancy', 'consistency.state_missing', 'consistency.state_needs_previous', 'consistency.state_ok', 'consistency.state_ok_auditor', 'consistency.state_ok_author', 'consistency.state_pending', 'consistency.title', 'consistency.valid']


def test_scene_consistency_texts_exist_in_both_languages():
    catalogs = json.loads((ROOT / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))
    for language in ('uk', 'en'):
        for key in CONSISTENCY_KEYS:
            assert catalogs[language].get(key), (language, key)
