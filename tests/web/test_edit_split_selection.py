"""EDIT-SENTENCE-GROUPS-S05: split_groups travels from the routes to the storage recheck and the decision."""
import threading

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.authoring.blueprints import save_role_settings
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.generation.test_edit_classification import Gateway

SOURCE = 'Boris скинув важкий робочий жилет на стілець та розстібнув комір комбінезона, що з тихим шелестом відійшов від шкіри.'
CANDIDATE = 'Борис скинув важкий робочий жилет на стілець і розстебнув комір комбінезона; тканина з тихим шелестом відійшла від шкіри.'
# Only the second edit accepted: the name stays as the author wrote it.
PARTIAL = 'Boris скинув важкий робочий жилет на стілець і розстебнув комір комбінезона; тканина з тихим шелестом відійшла від шкіри.'


def copyedit_case(tmp_path):
    repo = Repository(tmp_path); story = repo.create_story(StoryCreate(title='Тест'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    draft = repo.save_version(story.id, scene.id, 'draft', SOURCE, [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    settings = RoleSettings(provider=ProviderSettings(model='writer-fake'), edit_mode='diff')
    save_role_settings(repo, story.id, 'editor', settings, repo.get_story(story.id).revision)
    attempt = execute_stage(repo, scene.id, 'edit', build_context(repo, scene.id, 'edit', settings), Gateway(CANDIDATE), threading.Event(), lambda _: None)
    return repo, scene, attempt


def rewrite_case_with(tmp_path):
    from storygen.authoring.comments import CommentPayload, comment_fingerprint
    from storygen.generation.assisted_writing import build_rewrite_context
    from storygen.run_models import RunRequest
    repo = Repository(tmp_path); story = repo.create_story(StoryCreate(title='Тест'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='Борис знімає жилет.'))
    source = repo.save_version(story.id, scene.id, 'draft', SOURCE, [], content_format='markdown')
    repo.set_head(scene.id, 'draft', source.id, scene.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake-writer', response_mode='json_schema'), context_tokens=32768, max_output_tokens=4096)
    save_role_settings(repo, story.id, 'writer', role, repo.get_story(story.id).revision)
    scene = repo.get_scene(scene.id)
    saved = repo.save_draft_with_comments(scene.id, SOURCE, 'markdown', scene.revision, 0,
        CommentPayload(general='Виправити мову.', comments=[]), expected_source_version_id=source.id)
    notes = saved['comment_set']
    request = RunRequest(story_id=story.id, scene_id=scene.id, mode='rewrite', source_version_id=source.id, comment_set_id=notes.id, comment_fingerprint=comment_fingerprint(notes, source))
    attempt = execute_stage(repo, scene.id, 'rewrite', build_rewrite_context(repo, request), Gateway(CANDIDATE), threading.Event(), lambda _: None)
    return repo, scene, notes, attempt


def test_copyedit_partial_sentence_needs_split_groups(tmp_path):
    repo, scene, attempt = copyedit_case(tmp_path)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        url = f'/api/scenes/{scene.id}/copyedits/{attempt.id}'
        p = client.get(url).json()
        (group,) = p['groups']
        assert group['units'] == [[0], [1]]
        body = dict(expected_revision=p['expected_revision'], proposal_fingerprint=p['proposal_fingerprint'], selected_indices=[1])
        for suffix in ['/selection-preview', '']:
            old = client.post(url + suffix, json=body)
            assert old.status_code == 400 and 'Взаємозалежні правки речення' in old.json()['detail']
        bad = client.post(url + '/selection-preview', json={**body, 'split_groups': [1]})
        assert bad.status_code == 400 and 'Розділити можна лише' in bad.json()['detail']
        assert not repo.get_scene(scene.id).heads.get('prose')
        preview = client.post(url + '/selection-preview', json={**body, 'split_groups': [0]})
        assert preview.status_code == 200 and preview.json()['text'] == PARTIAL
        applied = client.post(url, json={**body, 'split_groups': [0, 0]})
        assert applied.status_code == 200
        assert repo.read_text(applied.json()['version']['id']) == PARTIAL
    decision = repo.get_attempt(attempt.id).context['copyedit_decisions'][-1]
    assert decision['selected_indices'] == [1] and decision['split_groups'] == [0]


def test_copyedit_storage_recheck_receives_split(tmp_path):
    from storygen.generation import copyedit_review
    repo, scene, attempt = copyedit_case(tmp_path)
    seen = []
    original = repo.commit_copyedit_selection

    def spy(*args):
        seen.append(args[-1])
        return original(*args)
    repo.commit_copyedit_selection = spy
    p = copyedit_review.copyedit_preview(repo, scene.id, attempt.id)
    copyedit_review.select_copyedits(repo, scene.id, attempt.id, [1], p['expected_revision'], p['proposal_fingerprint'], [0])
    assert seen == [[0]]
    scene_after = repo.get_scene(scene.id)
    assert repo.read_text(scene_after.heads['prose']) == PARTIAL
    decision = repo.get_attempt(attempt.id).context['copyedit_decisions'][-1]
    assert decision['selected_indices'] == [1] and decision['split_groups'] == [0]
    assert decision['result_version_id'] == scene_after.heads['prose']


def test_copyedit_storage_rejects_partial_group_without_split(tmp_path):
    from storygen.generation import copyedit_review
    repo, scene, attempt = copyedit_case(tmp_path)
    p = copyedit_review.copyedit_preview(repo, scene.id, attempt.id)
    calls = []
    original = repo.commit_copyedit_selection

    def drop_split(*args):
        # The service passed its own check with split; storage must recheck with the split it receives.
        calls.append(args)
        return original(*args[:-1])
    repo.commit_copyedit_selection = drop_split
    with pytest.raises(ValueError, match='Взаємозалежні правки речення'):
        copyedit_review.select_copyedits(repo, scene.id, attempt.id, [1], p['expected_revision'], p['proposal_fingerprint'], [0])
    assert calls and not repo.get_scene(scene.id).heads.get('prose')


def test_rewrite_partial_sentence_needs_split_groups(tmp_path):
    repo, scene, notes, attempt = rewrite_case_with(tmp_path)
    client = TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'missing.env')), base_url='http://127.0.0.1')
    base = f'/api/scenes/{scene.id}/rewrites/{attempt.id}'
    p = client.get(base).json()
    (group,) = p['groups']
    assert group['units'] == [[0], [1]]
    body = dict(selected_indices=[1], expected_revision=p['expected_revision'], proposal_fingerprint=p['proposal_fingerprint'], expected_comments_revision=notes.revision)
    for suffix in ['/selection-preview', '/apply']:
        old = client.post(base + suffix, json=body)
        assert old.status_code == 400 and 'Взаємозалежні правки речення' in old.json()['detail']
    preview = client.post(base + '/selection-preview', json={**body, 'split_groups': [0]})
    assert preview.status_code == 200 and preview.json()['text'] == PARTIAL
    applied = client.post(base + '/apply', json={**body, 'split_groups': [0]})
    assert applied.status_code == 200 and repo.read_text(applied.json()['version']['id']) == PARTIAL
    decision = repo.get_attempt(attempt.id).context['rewrite_decisions'][-1]
    assert decision['selected_indices'] == [1] and decision['split_groups'] == [0]


def test_rewrite_storage_recheck_uses_split(tmp_path):
    from storygen.generation.rewrite_review import rewrite_preview
    from storygen.storage.rewrite_store import publish_rewrite_selection
    repo, scene, notes, attempt = rewrite_case_with(tmp_path)
    p = rewrite_preview(repo, scene.id, attempt.id)
    args = (repo, scene.id, attempt.id, [1], p['expected_revision'], p['proposal_fingerprint'], notes.revision)
    with pytest.raises(ValueError, match='Взаємозалежні правки речення'):
        publish_rewrite_selection(*args)
    result = publish_rewrite_selection(*args, [0])
    assert repo.read_text(result['version'].id) == PARTIAL
