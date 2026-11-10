"""STORY-LANGUAGE-S04: switching a scene's prose language stales only material built for that language (#32)."""
import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import build_dependency_snapshot, resolve_freshness

LANGUAGE_SCOPES = ['draft', 'prose_edit', 'patches', 'author_rewrite']
STAGES = {'brief': ('brief', 'prose'), 'draft': ('draft', 'prose'), 'prose_edit': ('edit', 'prose'),
          'patches': ('edit', 'patches'), 'author_rewrite': ('rewrite', 'prose'), 'memory': ('memory', 'prose')}


def role(edit_mode='prose'):
    return RoleSettings(provider=ProviderSettings(model='fake'), edit_mode=edit_mode)


def setup(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Language'))
    scene = repo.create_scene(story.id, SceneCreate(title='Scene', beats='Events'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Draft', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    return repo, story.id, scene.id, draft


def snapshot_for(repo, story_id, scene_id, scope, draft_id):
    stage, mode = STAGES[scope]
    refs = [draft_id] if scope in {'prose_edit', 'patches', 'author_rewrite'} else []
    snapshot = build_dependency_snapshot(repo.context_view(story_id), scene_id, stage, role(mode), refs)
    assert snapshot.scope == scope
    return snapshot, refs


def save(repo, story_id, scene_id, scope, draft_id, strip=False):
    snapshot, refs = snapshot_for(repo, story_id, scene_id, scope, draft_id)
    if strip:
        snapshot.selectors = [s for s in snapshot.selectors if s.field != 'prose_language']
    kind = {'brief': 'brief', 'draft': 'draft'}.get(scope, 'edited')
    return repo.save_version(story_id, scene_id, kind, 'Result', refs, dependency_snapshot=snapshot)


def stale(repo, story_id, version_id):
    return resolve_freshness(repo.context_view(story_id), version_id).stale


def switch(repo, scene_id, value):
    language = None if value == 'story' else value
    # The API maps 'story' to None (STORY-LANGUAGE-S01, tests/storage/test_story_language.py).
    return repo.update_scene_metadata(scene_id, {'prose_language': language}, repo.get_scene(scene_id).revision)


@pytest.mark.req('STORY-LANGUAGE')
def test_selector_recorded_for_prose_scopes(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    for scope in LANGUAGE_SCOPES:
        snapshot, _ = snapshot_for(repo, story_id, scene_id, scope, draft.id)
        selectors = [s for s in snapshot.selectors if s.field == 'prose_language']
        assert [(s.kind, s.owner_id, s.expected) for s in selectors] == [('scene', scene_id, 'uk')], scope


@pytest.mark.req('STORY-LANGUAGE')
def test_switching_scene_language_stales_draft_not_brief(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    brief = save(repo, story_id, scene_id, 'brief', draft.id)
    versions = {scope: save(repo, story_id, scene_id, scope, draft.id) for scope in LANGUAGE_SCOPES}
    assert not stale(repo, story_id, brief.id)
    assert not any(stale(repo, story_id, v.id) for v in versions.values())
    switch(repo, scene_id, 'en')
    assert not stale(repo, story_id, brief.id)
    for scope, version in versions.items():
        assert stale(repo, story_id, version.id), scope


@pytest.mark.req('STORY-LANGUAGE')
def test_switch_back_restores_freshness(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    version = save(repo, story_id, scene_id, 'draft', draft.id)
    switch(repo, scene_id, 'en')
    assert stale(repo, story_id, version.id)
    switch(repo, scene_id, 'story')
    assert not stale(repo, story_id, version.id)


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('scope', LANGUAGE_SCOPES)
def test_legacy_snapshot_without_selector_treated_as_uk(tmp_path, scope):
    repo, story_id, scene_id, draft = setup(tmp_path)
    version = save(repo, story_id, scene_id, scope, draft.id, strip=True)
    assert not stale(repo, story_id, version.id)
    switch(repo, scene_id, 'en')
    assert stale(repo, story_id, version.id)


@pytest.mark.req('STORY-LANGUAGE')
def test_author_text_without_snapshot_not_checked(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    manual = repo.save_version(story_id, scene_id, 'manual', 'Author text', [])
    switch(repo, scene_id, 'en')
    assert not stale(repo, story_id, manual.id)


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('scope', ['brief', 'memory'])
def test_selector_not_recorded_for_brief_and_memory(tmp_path, scope):
    repo, story_id, scene_id, draft = setup(tmp_path)
    if scope == 'memory':
        prose = repo.save_version(story_id, scene_id, 'manual', 'Prose', [])
        repo.set_head(scene_id, 'prose', prose.id, repo.get_scene(scene_id).revision)
    snapshot, _ = snapshot_for(repo, story_id, scene_id, scope, draft.id)
    assert not any(s.field == 'prose_language' for s in snapshot.selectors)
