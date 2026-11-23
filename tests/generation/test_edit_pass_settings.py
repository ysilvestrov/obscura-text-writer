"""EDIT-LOOP: the edit pass limit of a run comes from the editor settings when the request has none."""
import json

import pytest
from pydantic import ValidationError

from storygen.domain import SceneCreate, StoryCreate
from storygen.storage.repository import Repository
from storygen.authoring.blueprints import get_role_settings, save_role_settings
from storygen.generation.edit_pass import resolve_edit_pass_limit
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.run_models import RunRequest
from tests.generation.test_readiness_single_view import seeded


def set_editor(repo, story_id, **fields):
    save_role_settings(repo, story_id, 'editor', RoleSettings(provider=ProviderSettings(model='editor'), **fields),
                       repo.get_story(story_id).revision)


def loop_request(story, scene, **fields):
    return RunRequest(story_id=story.id, scene_id=scene.id, mode='edit_loop', **fields)


@pytest.mark.req('EDIT-LOOP')
def test_role_settings_default_and_bounds():
    assert RoleSettings(provider=ProviderSettings(model='m')).edit_pass_limit == 5
    with pytest.raises(ValidationError):
        RoleSettings(provider=ProviderSettings(model='m'), edit_pass_limit=11)
    with pytest.raises(ValidationError):
        RoleSettings(provider=ProviderSettings(model='m'), edit_pass_limit=0)


@pytest.mark.req('EDIT-LOOP')
def test_old_editor_settings_read_as_five(tmp_path):
    repo, story, _ = seeded(tmp_path)
    with repo.db.connection() as db:
        payload = json.loads(db.execute("SELECT payload FROM role_settings WHERE story_id=? AND role='editor'",
                                        (story.id,)).fetchone()[0])
        payload.pop('edit_pass_limit', None)
        db.execute("UPDATE role_settings SET payload=? WHERE story_id=? AND role='editor'", (json.dumps(payload), story.id))
    assert get_role_settings(repo, story.id)['editor'].edit_pass_limit == 5


@pytest.mark.req('EDIT-LOOP')
def test_request_without_limit_takes_the_editor_setting(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    set_editor(repo, story.id, edit_pass_limit=2)
    assert loop_request(story, scenes[0]).edit_pass_limit is None
    assert resolve_edit_pass_limit(repo, loop_request(story, scenes[0])).edit_pass_limit == 2


@pytest.mark.req('EDIT-LOOP')
def test_explicit_limit_wins(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    set_editor(repo, story.id, edit_pass_limit=2)
    request = loop_request(story, scenes[0], edit_pass_limit=7)
    assert resolve_edit_pass_limit(repo, request) is request


@pytest.mark.req('EDIT-LOOP')
def test_story_without_an_editor_role_gives_five(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Без редактора'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='План'))
    save_role_settings(repo, story.id, 'writer', RoleSettings(provider=ProviderSettings(model='w')), repo.get_story(story.id).revision)
    assert resolve_edit_pass_limit(repo, loop_request(story, scene)).edit_pass_limit == 5


@pytest.mark.req('EDIT-LOOP')
def test_enqueued_run_stores_the_number(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ліміт'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Перше речення.', [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    set_editor(repo, story.id, edit_pass_limit=3, edit_mode='patches')
    run = RunCoordinator(repo).enqueue(loop_request(story, scene), 'pass-limit-1')
    assert repo.get_run(run.id).request.edit_pass_limit == 3


@pytest.mark.req('EDIT-LOOP')
def test_scene_readiness_uses_the_setting(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    set_editor(repo, story.id, edit_pass_limit=2)
    operation = RunCoordinator(repo).readiness(story.id, scenes[0].id, operation='scene')['operations']['scene']
    assert operation['edit_pass_limit'] == 2


@pytest.mark.req('EDIT-LOOP')
def test_repeated_request_id_keeps_its_stored_limit_after_a_settings_change(tmp_path):
    repo, story, scenes = seeded(tmp_path)
    worker = RunCoordinator(repo)
    request = RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='stage', stage='brief')
    run = worker.enqueue(request, 'same-id')
    set_editor(repo, story.id, edit_pass_limit=2)
    assert worker.enqueue(request, 'same-id').id == run.id
    assert worker.cancel_request(request, 'same-id').id == run.id
    assert repo.get_run(run.id).request.edit_pass_limit == 5


@pytest.mark.req('EDIT-LOOP')
def test_context_fingerprint_does_not_depend_on_the_pass_limit(tmp_path, monkeypatch):
    """Stored fingerprints were made before the field existed; it does not change the model request."""
    from storygen.generation import context as module
    from storygen.generation.context import build_context
    from tests.generation.test_role_routing import R, make_repo, writer_without_variant
    repo, item = make_repo(tmp_path, R(0, 1, 1))
    role = writer_without_variant('local/main')
    seen = []
    real = module.json.dumps
    monkeypatch.setattr(module.json, 'dumps', lambda obj, *a, **k: (seen.append(obj), real(obj, *a, **k))[1])
    base = build_context(repo, item.id, 'draft', role).fingerprint
    assert build_context(repo, item.id, 'draft', role.model_copy(update={'edit_pass_limit': 2})).fingerprint == base
    payloads = [o['settings'] for o in seen if isinstance(o, dict) and 'settings' in o and 'system' in o]
    assert payloads and all('edit_pass_limit' not in p for p in payloads)
