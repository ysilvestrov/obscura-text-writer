import json

import pytest
from pydantic import ValidationError

from storygen.generation.models import WritersBrief
from storygen.generation.planner_output import parse_planner_output,PlannerProtocolError
from tests.generation.test_planner_output import run_output


WRAPPER_WARNING = 'Знято одну зовнішню обгортку JSON планувальника; оригінальну відповідь збережено без змін.'
WARNING = 'Планувальник: структуровані proposed_changes перетворено на текст із номерами сцен; пропозиції потребують явного прийняття.'


@pytest.mark.parametrize('opening,closing,expected_warnings', [('', '', [WARNING]), ('```json\n', '\n```', [WRAPPER_WARNING, WARNING]), ("'", "'", [WRAPPER_WARNING, WARNING])])
def test_structured_model_proposals_preserve_text_number_and_review_gate(tmp_path, opening, closing, expected_warnings):
    change = "  Зберегти пам'ять і `цитату`.\nІнша деталь.  "
    payload = {'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': ['Рядок', {'scene_number': 2, 'change': change}, {'scene_number': 2, 'change': change}]}
    raw = opening + json.dumps(payload, ensure_ascii=False) + closing
    repo, scene, attempt = run_output(tmp_path, raw)
    assert attempt.state == 'needs_review', attempt.error
    assert 'brief' not in repo.get_scene(scene.id).heads
    saved = WritersBrief.model_validate_json(repo.read_text(attempt.result_version_id))
    assert saved.proposed_changes == ['Рядок', f'Сцена 2: {change}', f'Сцена 2: {change}']
    assert attempt.context['planner_warnings'] == expected_warnings
    assert repo.files.read_partial(attempt.partial_path) == raw
    with pytest.raises(ValidationError) as error:
        WritersBrief.model_validate(payload)
    assert [(e['type'],e['loc']) for e in error.value.errors()]==[('string_type',('proposed_changes',1)),('string_type',('proposed_changes',2))]


@pytest.mark.parametrize('proposal', [
    {'scene_number': 2, 'change': 'Текст', 'extra': 'Невідоме'},
    {'change': 'Текст'}, {'scene_number': 2},
    {'scene_number': True, 'change': 'Текст'}, {'scene_number': '2', 'change': 'Текст'},
    {'scene_number': 0, 'change': 'Текст'}, {'scene_number': -1, 'change': 'Текст'},
    {'scene_number': 2, 'change': ''}, {'scene_number': 2, 'change': '  '},
    {'scene_number': 2, 'change': {'text': 'Текст'}}, None, 3,
])
def test_unknown_model_proposals_remain_strict(tmp_path,proposal):
    warnings = []
    raw = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [proposal]}, ensure_ascii=False)
    with pytest.raises(ValidationError) as error:
        parse_planner_output(raw, 'brief', warnings)
    assert [(e['type'],e['loc']) for e in error.value.errors()]==[('string_type',('proposed_changes',0))]
    assert warnings == []
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed' and attempt.result_version_id is None
    assert attempt.context['planner_failure']['category']=='schema'
    assert 'brief' not in repo.get_scene(scene.id).heads


def test_plain_string_proposals_keep_exact_version_bytes():
    raw = '{ "objective": "Мета", "beats": ["Подія"], "proposed_changes": ["Сцена 2: Текст"] }'
    warnings = []
    _, content = parse_planner_output(raw, 'brief', warnings)
    assert content == raw
    assert warnings == []


@pytest.mark.parametrize('opening,closing,expected_warnings', [('', '', [WARNING]), ('```json\n', '\n```', [WRAPPER_WARNING, WARNING]), ("'", "'", [WRAPPER_WARNING, WARNING])])
def test_structured_proposal_warning_survives_worker_reload(tmp_path,opening,closing,expected_warnings):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator, RunRequest
    from storygen.providers.streaming import GenerationEvent
    from storygen.storage.repository import Repository
    from storygen.web.localization import diagnostic
    from tests.generation.test_scene_pipeline import prepare

    repo, scene, _, roles = prepare(tmp_path)
    save_role_settings(repo, scene.story_id, 'planner', roles['planner'], repo.get_story(scene.story_id).revision)
    raw = opening + json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [{'scene_number': 2, 'change': 'Текст'}]}) + closing

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
    assert saved.state == 'needs_review' and saved.warning == '\n'.join(expected_warnings)
    assert 'brief' not in reopened.get_scene(scene.id).heads
    assert gateway.calls == 1
    attempts=reopened.list_attempts(scene.story_id,run.id)
    assert len(attempts)==1
    assert attempts[0].state=='needs_review' and attempts[0].context['planner_warnings']==expected_warnings
    assert reopened.files.read_partial(attempts[0].partial_path)==raw
    assert [e.data for e in reopened.list_run_events(run.id) if e.type == 'context_warning'] == [{'warnings': expected_warnings, 'stage': 'brief', 'scene_id': scene.id}]
    assert diagnostic(WARNING, 'en') == 'Planner: structured proposed_changes were converted to text with scene numbers; proposals require explicit acceptance.'


def test_mixed_invalid_proposals_do_not_partially_normalize_or_warn():
    raw = json.dumps({'objective': 'Мета', 'beats': ['Подія'], 'proposed_changes': [{'scene_number': 2, 'change': 'Текст'}, {'scene_number': 3, 'change': None}]})
    warnings = []
    with pytest.raises(ValidationError) as error:
        parse_planner_output(raw, 'brief', warnings)
    assert [(e['type'],e['loc']) for e in error.value.errors()]==[('string_type',('proposed_changes',1))]
    assert warnings == []


def test_duplicate_keys_inside_structured_proposals_stay_rejected():
    raw = '{"objective":"Мета","beats":["Подія"],"proposed_changes":[{"scene_number":2,"scene_number":3,"change":"Текст"}]}'
    with pytest.raises(PlannerProtocolError, match='^duplicate_key$'):
        parse_planner_output(raw, 'brief', [])


@pytest.mark.parametrize('structured',[False,True])
@pytest.mark.parametrize('field',['objective','change'])
def test_invalid_unicode_remains_schema_failure_with_original_partial(tmp_path,structured,field):
    value='\ud800'
    change=value if field=='change' else 'Текст'
    proposal={'scene_number':2,'change':change} if structured else change
    raw=json.dumps({'objective':value if field=='objective' else 'Мета','beats':['Подія'],'proposed_changes':[proposal]})
    repo,scene,attempt=run_output(tmp_path,raw)
    assert attempt.state=='failed' and attempt.result_version_id is None
    assert attempt.context['planner_failure']['category']=='schema'
    assert 'brief' not in repo.get_scene(scene.id).heads


def test_prepare_does_not_accept_brief_proposal_wire_shape():
    raw=json.dumps({'canon':'Канон','characters':[],'scenes':[{'title':'Сцена'}],'proposed_changes':[{'scene_number':2,'change':'Текст'}]})
    with pytest.raises(ValidationError) as error:
        parse_planner_output(raw,'prepare',[])
    assert [(e['type'],e['loc']) for e in error.value.errors()]==[('extra_forbidden',('proposed_changes',))]


def test_manual_brief_endpoint_rejects_structured_wire_without_creating_version(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    from tests.generation.test_scene_pipeline import prepare
    repo,scene,_,_=prepare(tmp_path)
    before=[v.id for v in repo.list_versions(scene.story_id,scene.id)]
    raw=json.dumps({'objective':'Мета','beats':['Подія'],'proposed_changes':[{'scene_number':2,'change':'Текст'}]})
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        result=client.post(f'/api/scenes/{scene.id}/brief',json={'text':raw,'expected_revision':repo.get_scene(scene.id).revision})
    assert result.status_code==400
    assert [v.id for v in repo.list_versions(scene.story_id,scene.id)]==before
    assert 'brief' not in repo.get_scene(scene.id).heads
