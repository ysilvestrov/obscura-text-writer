import pytest
from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.impact.planning import capture_target
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import build_dependency_snapshot, resolve_freshness

pytestmark = pytest.mark.unrated_stories  # first-set semantics need stories created unrated

RATING_SCOPES = ['brief', 'draft', 'prose_edit', 'patches', 'author_rewrite']


def R(s, v, t):
    return ContentRating(sexual=s, violence=v, themes=t)


def role(edit_mode='prose'):
    return RoleSettings(provider=ProviderSettings(model='fake'), edit_mode=edit_mode)


def setup(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Рейтинг'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='Події'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Чернетка', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    return repo, story.id, scene.id, draft


def snapshot_for(repo, story_id, scene_id, scope, draft_id):
    stage, mode = {
        'brief': ('brief', 'prose'), 'draft': ('draft', 'prose'), 'prose_edit': ('edit', 'prose'),
        'patches': ('edit', 'patches'), 'author_rewrite': ('rewrite', 'prose'), 'memory': ('memory', 'prose'),
    }[scope]
    refs = [draft_id] if scope in {'prose_edit', 'patches', 'author_rewrite'} else []
    snapshot = build_dependency_snapshot(repo.context_view(story_id), scene_id, stage, role(mode), refs)
    assert snapshot.scope == scope
    return snapshot, refs


def save(repo, story_id, scene_id, scope, draft_id, strip_rating=False):
    snapshot, refs = snapshot_for(repo, story_id, scene_id, scope, draft_id)
    if strip_rating:
        snapshot.selectors = [s for s in snapshot.selectors if s.field != 'content_rating']
    kind = {'brief': 'brief', 'draft': 'draft'}.get(scope, 'edited')
    return repo.save_version(story_id, scene_id, kind, 'Результат', refs, dependency_snapshot=snapshot)


def fresh(repo, story_id, version_id):
    return resolve_freshness(repo.context_view(story_id), version_id)


def set_story(repo, story_id, rating):
    return repo.update_story_rating(story_id, rating, repo.get_story(story_id).revision)


def set_scene(repo, scene_id, rating):
    return repo.update_scene_rating(scene_id, rating, repo.get_scene(scene_id).revision)


def rating_selectors(snapshot):
    return [s for s in snapshot.selectors if s.field == 'content_rating']


def test_rating_selector_recorded_for_generation_scopes(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(2, 1, 0))
    set_scene(repo, scene_id, R(1, 2, 1))
    for scope in RATING_SCOPES:
        snapshot, _ = snapshot_for(repo, story_id, scene_id, scope, draft.id)
        [selector] = rating_selectors(snapshot)
        assert (selector.kind, selector.owner_id, selector.expected) == ('scene', scene_id, ['1', '2', '1'])
    memory, _ = snapshot_for(repo, story_id, scene_id, 'memory', draft.id)
    assert not rating_selectors(memory)
    manual = save_manual_prose(repo, scene_id, 'Авторський текст', repo.get_scene(scene_id).revision)
    snapshot = repo.get_version(manual.id).dependency_snapshot
    assert snapshot.scope == 'author_text' and not rating_selectors(snapshot)


def test_rating_selector_records_story_rating_without_override(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    snapshot, _ = snapshot_for(repo, story_id, scene_id, 'draft', draft.id)
    assert rating_selectors(snapshot)[0].expected is None
    set_story(repo, story_id, R(2, 0, 1))
    snapshot, _ = snapshot_for(repo, story_id, scene_id, 'draft', draft.id)
    assert rating_selectors(snapshot)[0].expected == ['2', '0', '1']


@pytest.mark.parametrize('scope', RATING_SCOPES)
@pytest.mark.parametrize('lowered', [R(0, 2, 2), R(2, 0, 2), R(2, 2, 0)])
def test_lowering_makes_stale_raising_keeps_fresh(tmp_path, scope, lowered):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(1, 1, 1))
    version = save(repo, story_id, scene_id, scope, draft.id)
    assert not fresh(repo, story_id, version.id).stale
    set_scene(repo, scene_id, R(2, 1, 2))
    assert not fresh(repo, story_id, version.id).stale
    set_story(repo, story_id, R(2, 2, 2))
    set_scene(repo, scene_id, None)
    assert not fresh(repo, story_id, version.id).stale
    set_story(repo, story_id, lowered)
    result = fresh(repo, story_id, version.id)
    assert result.stale
    change = next(c for c in result.reasons if c.selector and c.selector.field == 'content_rating')
    assert change.reason == 'selector_changed'
    assert change.current == [str(lowered.sexual), str(lowered.violence), str(lowered.themes)]


def test_old_snapshot_uses_initial_rating(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    version = save(repo, story_id, scene_id, 'draft', draft.id, strip_rating=True)
    assert not rating_selectors(repo.get_version(version.id).dependency_snapshot)
    assert not fresh(repo, story_id, version.id).stale
    set_story(repo, story_id, R(2, 1, 1))
    assert not fresh(repo, story_id, version.id).stale
    set_story(repo, story_id, R(1, 1, 1))
    result = fresh(repo, story_id, version.id)
    assert result.stale
    change = next(c for c in result.reasons if c.selector and c.selector.field == 'content_rating')
    assert (change.reason, change.expected, change.current) == ('selector_changed', ['2', '1', '1'], ['1', '1', '1'])
    set_story(repo, story_id, R(2, 1, 1))
    assert not fresh(repo, story_id, version.id).stale


def test_old_patches_snapshot_uses_initial_rating(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    version = save(repo, story_id, scene_id, 'patches', draft.id, strip_rating=True)
    set_story(repo, story_id, R(1, 1, 1))
    assert not fresh(repo, story_id, version.id).stale
    set_scene(repo, scene_id, R(1, 0, 1))
    assert fresh(repo, story_id, version.id).stale


def test_author_text_never_stale_from_rating(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(2, 2, 2))
    manual = save_manual_prose(repo, scene_id, 'Авторський текст', repo.get_scene(scene_id).revision)
    assert not fresh(repo, story_id, manual.id).stale
    set_story(repo, story_id, R(0, 0, 0))
    set_scene(repo, scene_id, R(0, 0, 0))
    assert not fresh(repo, story_id, manual.id).stale


def test_unrated_snapshot_uses_initial_rating(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    version = save(repo, story_id, scene_id, 'draft', draft.id)
    assert rating_selectors(repo.get_version(version.id).dependency_snapshot)[0].expected is None
    set_story(repo, story_id, R(2, 1, 1))
    assert not fresh(repo, story_id, version.id).stale
    set_story(repo, story_id, R(1, 1, 1))
    result = fresh(repo, story_id, version.id)
    change = next(c for c in result.reasons if c.selector and c.selector.field == 'content_rating')
    assert result.stale and (change.expected, change.current) == (['2', '1', '1'], ['1', '1', '1'])
    set_story(repo, story_id, R(2, 1, 1))
    assert not fresh(repo, story_id, version.id).stale


def test_story_lowering_below_scene_override_keeps_scene_fresh(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(2, 2, 2))
    set_scene(repo, scene_id, R(1, 1, 1))
    version = save(repo, story_id, scene_id, 'draft', draft.id)
    set_story(repo, story_id, R(0, 0, 0))
    assert not fresh(repo, story_id, version.id).stale


def test_impact_capture_ignores_rating_raise(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(1, 1, 1))
    version = save(repo, story_id, scene_id, 'prose_edit', draft.id)
    repo.set_head(scene_id, 'prose', version.id, repo.get_scene(scene_id).revision)
    before = capture_target(repo.context_view(story_id), version.id)
    set_story(repo, story_id, R(2, 2, 2))
    after = capture_target(repo.context_view(story_id), version.id)
    assert after.fingerprint == before.fingerprint
    change = next(c for c in after.changes if c.input_field == 'content_rating')
    assert not change.changed
    assert next(s for s in after.selectors if s['field'] == 'content_rating')['expected'] == ['1', '1', '1']


def test_impact_preview_tolerates_rating_selector(tmp_path):
    repo, story_id, scene_id, draft = setup(tmp_path)
    set_story(repo, story_id, R(2, 2, 2))
    version = save(repo, story_id, scene_id, 'prose_edit', draft.id)
    repo.set_head(scene_id, 'prose', version.id, repo.get_scene(scene_id).revision)
    set_story(repo, story_id, R(1, 2, 2))
    target = capture_target(repo.context_view(story_id), version.id)
    assert target.blockers == []
    change = next(c for c in target.changes if c.input_field == 'content_rating')
    assert change.changed and change.owner_id == scene_id
    live = next(s for s in target.selectors if s['field'] == 'content_rating')
    assert live['expected'] == ['1', '2', '2']
