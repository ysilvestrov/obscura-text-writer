import json

import pytest

from storygen.generation.models import WritersBrief
from storygen.generation.planner_output import parse_planner_output
from tests.generation.test_planner_output import run_output


WARNING = 'Планувальник: структуровані proposed_changes перетворено на текст із номерами сцен; пропозиції потребують явного прийняття.'


@pytest.mark.parametrize('opening,closing', [('', ''), ('```json\n', '\n```'), ("'", "'")])
def test_structured_model_proposals_preserve_text_number_and_review_gate(tmp_path, opening, closing):
    change = "  Зберегти пам'ять і `цитату`.\nІнша деталь.  "
    payload = {'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': ['Рядок', {'scene_number': 2, 'change': change}, {'scene_number': 2, 'change': change}]}
    raw = opening + json.dumps(payload, ensure_ascii=False) + closing
    repo, scene, attempt = run_output(tmp_path, raw)
    assert attempt.state == 'needs_review', attempt.error
    assert 'brief' not in repo.get_scene(scene.id).heads
    saved = WritersBrief.model_validate_json(repo.read_text(attempt.result_version_id))
    assert saved.proposed_changes == ['Рядок', f'Сцена 2: {change}', f'Сцена 2: {change}']
    assert attempt.context['planner_warnings'][-1] == WARNING
    assert repo.files.read_partial(attempt.partial_path) == raw
    with pytest.raises(ValueError):
        WritersBrief.model_validate(payload)


@pytest.mark.parametrize('proposal', [
    {'scene_number': 2, 'change': 'Текст', 'extra': 'Невідоме'},
    {'change': 'Текст'}, {'scene_number': 2},
    {'scene_number': True, 'change': 'Текст'}, {'scene_number': '2', 'change': 'Текст'},
    {'scene_number': 0, 'change': 'Текст'}, {'scene_number': -1, 'change': 'Текст'},
    {'scene_number': 2, 'change': ''}, {'scene_number': 2, 'change': '  '},
    {'scene_number': 2, 'change': {'text': 'Текст'}}, None, 3,
])
def test_unknown_model_proposals_remain_strict(proposal):
    warnings = []
    raw = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [proposal]}, ensure_ascii=False)
    with pytest.raises(ValueError):
        parse_planner_output(raw, 'brief', warnings)
    assert warnings == []


def test_plain_string_proposals_keep_exact_version_bytes():
    raw = '{ "objective": "Мета", "beats": ["Подія"], "proposed_changes": ["Сцена 2: Текст"] }'
    warnings = []
    _, content = parse_planner_output(raw, 'brief', warnings)
    assert content == raw
    assert warnings == []


def test_structured_proposal_warning_survives_worker_reload(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator, RunRequest
    from storygen.providers.streaming import GenerationEvent
    from storygen.storage.repository import Repository
    from storygen.web.localization import diagnostic
    from tests.generation.test_scene_pipeline import prepare

    repo, scene, _, roles = prepare(tmp_path)
    save_role_settings(repo, scene.story_id, 'planner', roles['planner'], repo.get_story(scene.story_id).revision)
    raw = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [{'scene_number': 2, 'change': 'Текст'}]})

    class Gateway:
        calls = 0
        def stream(self, *_):
            self.calls += 1
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')

    gateway = Gateway()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='stage', stage='brief'), 'structured')
    worker._execute(run.id)
    reopened = Repository(tmp_path)
    saved = reopened.get_run(run.id)
    assert saved.state == 'needs_review' and saved.warning == WARNING
    assert 'brief' not in reopened.get_scene(scene.id).heads
    assert gateway.calls == 1
    assert [e.data for e in reopened.list_run_events(run.id) if e.type == 'context_warning'] == [{'warnings': [WARNING], 'stage': 'brief', 'scene_id': scene.id}]
    assert diagnostic(WARNING, 'en') == 'Planner: structured proposed_changes were converted to text with scene numbers; proposals require explicit acceptance.'


def test_mixed_invalid_proposals_do_not_partially_normalize_or_warn():
    raw = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [{'scene_number': 2, 'change': 'Текст'}, {'scene_number': 3, 'change': None}]})
    warnings = []
    with pytest.raises(ValueError):
        parse_planner_output(raw, 'brief', warnings)
    assert warnings == []


def test_duplicate_keys_inside_structured_proposals_stay_rejected():
    raw = '{"objective":"Мета","beats":["Подія"],"proposed_changes":[{"scene_number":2,"scene_number":3,"change":"Текст"}]}'
    with pytest.raises(ValueError, match='duplicate_key'):
        parse_planner_output(raw, 'brief', [])
