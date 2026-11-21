"""PERF-001-S05: one impact plan parses each cards and memory version once and derives the protagonists, names and
memory projection policy once per scene; the same plan as without the per-view memo; nothing survives the request."""
import collections
import json

import pytest

import storygen.characters.acquaintance as acquaintance
import storygen.characters.models as character_models
import storygen.characters.names as names
import storygen.memory.forwarding as forwarding
import storygen.memory.journal as journal
from storygen.application.workspace_bench import _publish_cards, build_story
from storygen.review.capture import plan_review
from storygen.storage.repository import Repository

SCENES = 6


@pytest.fixture(scope='module')
def cast_repo(tmp_path_factory):
    repo = Repository(tmp_path_factory.mktemp('cast'))
    return repo, build_story(repo, SCENES, cast=True)


def _count(monkeypatch):
    calls = collections.Counter()
    for module, name in [(character_models, 'load_characters'), (journal, 'load_memory'), (forwarding, '_projection_policy'),
                         (names, 'scene_names'), (acquaintance, 'protagonist')]:
        original = getattr(module, name)

        def counted(*args, _original=original, _name=name, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, counted)
    return calls


def test_cast_fixture_makes_every_head_stale_with_hidden_memory(cast_repo):
    repo, story_id = cast_repo
    view = repo.context_view(story_id)
    plan = plan_review(view)
    assert len(plan.targets) == SCENES and not any(t.blockers for t in plan.targets)
    assert any(forwarding.projection_policy(view, s.id) for s in view.peek_scenes(story_id))


def test_plan_parses_versions_once_and_derives_once_per_scene(cast_repo, monkeypatch):
    repo, story_id = cast_repo
    view = repo.context_view(story_id)
    cards = sum(1 for v in view.versions.values() if v.kind == 'character_cards')
    memories = sum(1 for v in view.versions.values() if v.kind == 'memory')
    calls = _count(monkeypatch)
    plan_review(view)
    assert calls['load_characters'] <= cards
    assert calls['load_memory'] <= memories
    assert calls['protagonist'] <= 1
    assert calls['scene_names'] <= SCENES
    assert calls['_projection_policy'] <= SCENES


def _without_memo(monkeypatch):
    from storygen.storage import context_view
    monkeypatch.setattr(context_view, 'memo', lambda source, key, build: build())


def test_memo_gives_the_same_plan(cast_repo, monkeypatch):
    repo, story_id = cast_repo
    memoized = plan_review(repo.context_view(story_id)).model_dump()
    _without_memo(monkeypatch)
    assert plan_review(repo.context_view(story_id)).model_dump() == memoized


def test_memo_does_not_survive_a_write(tmp_path):
    repo = Repository(tmp_path)
    story_id = build_story(repo, 3, cast=True)
    before = plan_review(repo.context_view(story_id))
    _publish_cards(repo, story_id, 'third')
    after = plan_review(repo.context_view(story_id))
    assert after.fingerprint != before.fingerprint
    current = repo.get_story(story_id).characters_version_id
    assert all(current in t.source_hashes for t in after.targets)


def test_plan_leaves_memoized_models_as_parsed(cast_repo):
    from storygen.application.workspace_bench import OPERATIONS, _request
    from storygen.generation.readiness import preview
    from storygen.impact.presentation import scene_status
    repo, story_id = cast_repo
    view = repo.context_view(story_id)
    plan_review(view)
    scene_status(view)
    middle = view.peek_scenes(story_id)[SCENES // 2].id
    for name in OPERATIONS:  # readiness of every operation on the same view, as RunCoordinator.readiness does
        preview(repo, _request(story_id, middle, name), view)
    assert any(key[0] == 'cards' for key in view.memo_cache) and any(key[0] == 'memory' for key in view.memo_cache)
    for key, value in view.memo_cache.items():
        if key[0] == 'cards':
            ref = view.versions[key[1]]
            fresh = character_models.load_characters(view.read_blob(ref.relative_path, ref.sha256).decode('utf-8'))
            assert [c.model_dump() for c in value] == [c.model_dump() for c in fresh]
        elif key[0] == 'memory' and key[2] == 'scene':
            ref = view.versions[key[1]]
            fresh = journal.load_memory(view.read_blob(ref.relative_path, ref.sha256).decode('utf-8'))
            assert json.dumps(value.model_dump(), sort_keys=True) == json.dumps(fresh.model_dump(), sort_keys=True)
