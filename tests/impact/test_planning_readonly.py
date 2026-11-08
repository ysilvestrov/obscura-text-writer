"""Review planning reads the view without copies and reuses equal reads within one request: same plan as the frozen
pre-change path, no view mutation, deep copies independent of the number of reads."""
import json

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.characters.models import CharacterEntry, CharacterRecord
from storygen.domain import SceneCreate, Scene, VersionRef
from storygen.generation.dependencies import save_manual_prose
from storygen.impact.planning import plan_impact
from storygen.impact.presentation import scene_status
from storygen.review.capture import plan_review
from storygen.storage.context_view import ContextView
from storygen.web.app import create_app
from tests.impact import reference_planning as reference
from tests.memory.test_forwarding import seeded as memory_seeded
from tests.storage.test_context_view_readonly import _dumps


def _cards(repo, story, text):
    card = CharacterRecord(id='maria', name='Марія', entries=[
        CharacterEntry(id='now', text=text, availability='timeless', origin='author')])
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps([card.model_dump()], ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)


def rich(root):
    """Memory journals on every scene, a stale chain, an accepted stale prose, a changed cast and cards, a trashed scene."""
    repo, story, scenes = memory_seeded(root)
    _cards(repo, story, 'Любить листи.')
    third = repo.get_scene(scenes[2].id)
    repo.update_scene_metadata(third.id, {'character_ids': ['maria']}, third.revision)
    save_manual_prose(repo, third.id, 'Марія читає. Побутова деталь номер 3.', repo.get_scene(third.id).revision)
    save_manual_prose(repo, scenes[0].id, 'Інша деталь номер 1.', repo.get_scene(scenes[0].id).revision)
    second = repo.get_scene(scenes[1].id)
    assert repo.get_version(second.heads['prose']).stale
    preview = repo.preview_acceptance(second.id, second.heads['prose'])
    repo.accept_version(second.id, second.heads['prose'], preview.expected_revision, preview.preview_fingerprint)
    _cards(repo, story, 'Уникає листів.')
    third = repo.get_scene(third.id)
    repo.update_scene_metadata(third.id, {'character_ids': ['maria', 'ivan']}, third.revision)
    trashed = repo.create_scene(story.id, SceneCreate(title='Кошик'))
    repo.set_scene_trashed(story.id, trashed.id, trashed.revision, restore=False)
    return repo, story


def cast_only(root):
    """Unchanged cards, changed cast: the same cards version is read with the old and the current cast."""
    from storygen.domain import StoryCreate
    from storygen.storage.repository import Repository
    repo = Repository(root)
    story = repo.create_story(StoryCreate(title='Склад'))
    cards = [CharacterRecord(id=id, name=id, entries=[CharacterEntry(id='e' + id, text='Опис ' + id, availability='timeless', origin='author')])
             for id in ['maria', 'ivan']]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps([c.model_dump() for c in cards], ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    first, second = [repo.create_scene(story.id, SceneCreate(title=t)) for t in ['Перша', 'Друга']]
    save_manual_prose(repo, first.id, 'Ранок.', 0)
    repo.update_scene_metadata(second.id, {'character_ids': ['maria']}, repo.get_scene(second.id).revision)
    prose = save_manual_prose(repo, second.id, 'Вечір.', repo.get_scene(second.id).revision)
    repo.update_scene_metadata(second.id, {'character_ids': ['maria', 'ivan']}, repo.get_scene(second.id).revision)
    assert repo.get_version(prose.id).stale
    return repo, story


def legacy_with_brief(root):
    """Legacy prose without a snapshot (current-consistency basis) and a stale historical brief of the same scene."""
    from storygen.storage.snapshots import build_author_baseline
    from tests.review.test_current_basis import legacy
    repo, story, first, second = legacy(root)[:4]
    snapshot = build_author_baseline(repo.context_view(story.id), second.id)
    brief = repo.save_version(story.id, second.id, 'brief', 'Бриф.', list(snapshot.refs), dependency_snapshot=snapshot)
    repo.set_head(second.id, 'brief', brief.id, repo.get_scene(second.id).revision)
    repo.update_scene_metadata(second.id, {'title': 'Нова назва'}, repo.get_scene(second.id).revision)
    assert repo.get_version(brief.id).stale
    return repo, story


def _plans(view):
    return json.dumps([plan_review(view).model_dump(), plan_impact(view).model_dump()], sort_keys=True, ensure_ascii=False)


def _reference_plans(view):
    return json.dumps([reference.plan_review(view).model_dump(), reference.plan_impact(view).model_dump()],
                      sort_keys=True, ensure_ascii=False)


def test_fixture_reaches_memory_cards_acceptance_and_cast_branches(tmp_path):
    repo, story = rich(tmp_path)
    view = repo.context_view(story.id)
    plan = plan_review(view)
    assert len(plan.targets) >= 2
    kinds = {view.versions[id].kind for t in plan.targets for id in t.source_hashes}
    assert {'memory', 'character_cards', 'manual'} <= kinds
    assert any(t.memory_text for t in plan.targets)
    assert any(c.changed and c.input_field == 'characters_version_id' for t in plan.targets for c in t.changes)
    assert any(c.changed and c.input_field == 'character_ids' for t in plan.targets for c in t.changes)
    assert view.acceptances and any(t.version_id in view.acceptances for t in plan.targets)


def test_plan_matches_frozen_copying_path(tmp_path):
    repo, story = rich(tmp_path / 'rich')
    seeded, story2 = memory_seeded(tmp_path / 'memory')[:2]
    save_manual_prose(seeded, seeded.list_scenes(story2.id)[0].id, 'Зміна.', seeded.list_scenes(story2.id)[0].revision)
    cast = cast_only(tmp_path / 'cast')
    current = legacy_with_brief(tmp_path / 'legacy')
    view = current[0].context_view(current[1].id)
    plan = plan_review(view)
    assert {t.material for t in plan.targets} == {'brief', 'prose'}
    assert any(reference.mode_for(view, t.version_id) == 'current_consistency' for t in plan.targets)
    target = plan_review(cast[0].context_view(cast[1].id)).targets[0]
    change = next(c for c in target.changes if c.input_field == 'characters_version_id')
    assert change.old_ref == change.new_ref and change.old_text != change.new_text
    for r, s in [(repo, story), (seeded, story2), cast, current]:
        assert _plans(r.context_view(s.id)) == _reference_plans(r.context_view(s.id))
        assert scene_status(r.context_view(s.id)) == reference.scene_status(r.context_view(s.id))


def test_overview_matches_frozen_copying_path(tmp_path, monkeypatch):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo, story = rich(tmp_path)
    del repo
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    fast = client.get(f'/api/stories/{story.id}/impact')
    assert fast.status_code == 200 and fast.json()['pending']
    import storygen.review.capture as capture
    import storygen.web.routes_impact as routes
    monkeypatch.setattr(capture, 'plan_review', reference.plan_review)
    monkeypatch.setattr(routes, 'scene_status', reference.scene_status)
    assert client.get(f'/api/stories/{story.id}/impact').json() == fast.json()


def test_planning_does_not_mutate_view(tmp_path):
    repo, story = rich(tmp_path)
    view = repo.context_view(story.id)
    before = (_dumps(view), [r.model_dump() for r in view.acceptance_records])
    first = _plans(view), scene_status(view)
    assert (_dumps(view), [r.model_dump() for r in view.acceptance_records]) == before
    assert (_plans(view), scene_status(view)) == first


def test_planning_deep_copies_do_not_grow_with_reads(tmp_path, monkeypatch):
    """Old path: a deep copy of a scene for every read and of every scene for each projection and journal check."""
    repo, story = rich(tmp_path)
    counts = {'deep': 0}
    for cls in (Scene, VersionRef):
        original = cls.model_copy

        def counting(self, *args, _original=original, **kwargs):
            if kwargs.get('deep'):
                counts['deep'] += 1
            return _original(self, *args, **kwargs)
        monkeypatch.setattr(cls, 'model_copy', counting)
    view = repo.context_view(story.id)
    reference.plan_review(view)
    old = counts['deep']
    counts['deep'] = 0
    view = repo.context_view(story.id)
    plan = plan_review(view)
    scenes = len(view.peek_scenes(story.id))
    # One scene copy per captured target and one effective_scene copy per scene; a current-consistency target adds
    # build_author_baseline (scene list, story version reads); none of them depends on the number of reads.
    current = sum(1 for t in plan.targets if reference.mode_for(view, t.version_id) == 'current_consistency')
    assert counts['deep'] <= len(plan.targets) + scenes + current * (scenes + 8)
    assert old > 3 * counts['deep']
    # scene_status: only effective_scene copies a scene (prose heads); heads are no longer copied by get_version.
    counts['deep'] = 0
    reference.scene_status(view)
    old_status = counts['deep']
    counts['deep'] = 0
    scene_status(view)
    assert counts['deep'] <= scenes < old_status
