import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository


def prepared(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Контракт'))
    scene = repo.create_scene(story.id, SceneCreate(title='Тест', beats='Анна чекає.'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Анна чекає.', [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    return repo, story, repo.get_scene(scene.id)


def test_legacy_prompt_blocks_context_before_request(tmp_path):
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Поверни прозу.', [])
    settings = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', prompt_version_id=prompt.id)
    with pytest.raises(ValueError, match='признач'):
        build_context(repo, scene.id, 'edit', settings)


def test_prose_prompt_cannot_be_used_for_patch_output(tmp_path):
    from storygen.generation.prompts import expected_contract
    repo, story, scene = prepared(tmp_path)
    settings = RoleSettings(provider=ProviderSettings(model='fake'))
    prompt = repo.save_version(story.id, None, 'prompt', 'Поверни прозу.', [],
                               prompt_contract=expected_contract('edit', settings))
    settings = settings.model_copy(update={'prompt_version_id': prompt.id, 'edit_mode': 'patches'})
    with pytest.raises(ValueError, match='edit/patches/1'):
        build_context(repo, scene.id, 'edit', settings)


def test_explicit_legacy_assignment_creates_new_immutable_prompt(tmp_path):
    from storygen.web.routes_settings import SettingsChange, configure_prompts
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Власна редактура.', [])
    settings = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', prompt_version_id=prompt.id)
    change = SettingsChange(expected_revision=repo.get_story(story.id).revision, role='editor',
                            settings=settings, confirm_prompt_contract=True)
    assigned = configure_prompts(repo, story.id, change, settings)
    assert assigned.prompt_version_id != prompt.id
    assert repo.get_version(prompt.id).prompt_contract is None
    assert repo.read_text(assigned.prompt_version_id) == 'Власна редактура.'
    context = build_context(repo, scene.id, 'edit', assigned)
    assert context.system_text == 'Власна редактура.'


def test_future_editor_prompt_blocks_run_preflight(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.readiness import preview
    from storygen.run_models import RunRequest
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Невідомий контракт.', [])
    for role in ['planner', 'writer', 'editor', 'memory']:
        # Seed legacy persisted settings directly: a migrated store must be checked at use too.
        settings = RoleSettings(provider=ProviderSettings(model='fake'), prompt_version_id=prompt.id if role == 'editor' else None)
        if role == 'editor':
            import json
            with repo.db.connection() as db:
                db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)', (story.id, role, settings.model_dump_json()))
        else:
            save_role_settings(repo, story.id, role, settings, repo.get_story(story.id).revision)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scene.id))
    assert not result['ready'] and 'признач' in result['reason']


def test_builtin_patch_prompt_needs_no_assignment(tmp_path):
    repo, _, scene = prepared(tmp_path)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches'))
    assert '"edits"' in context.system_text
