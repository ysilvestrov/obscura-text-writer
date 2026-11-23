"""PERF-001 / BOOK-LINEAGE (#39): the O(n) chain and the request-scoped lineage memo give the reference results; the
map of a structured book is built at most once per scope and never outlives it (neutral synthetic books)."""
import random

import pytest

from storygen.book import lineage as module
from storygen.book.lineage import (book_end_heads, lineage, lineage_map, lineage_scope, part_end_heads,
                                   previous_scenes)
from storygen.domain import Arc, BookStructure, Part, Scene, Story
from tests.book.lineage_reference import (reference_book_end_heads, reference_lineage_map,
                                          reference_part_end_heads, reference_previous_scenes)


def _book(kind, rng, n):
    scenes = [Scene(id=f's{i}', story_id='b', title=f'Сцена {i}', position=i) for i in range(n)]
    if rng.random() < 0.3:  # a position shared with the previous scene: reading order then depends on the input order
        j = rng.randrange(1, n)
        scenes[j] = scenes[j].model_copy(update={'position': scenes[j - 1].position})
    for s in rng.sample(scenes, rng.randrange(0, 3)):
        scenes[scenes.index(s)] = s.model_copy(update={'trashed_at': '2026-11-21T10:00:00+00:00'})
    if kind == 'none':
        return Story(id='b', title='Книга'), scenes
    if kind == 'one-arc':
        parts = [['A']]
    elif kind == 'sequential':
        parts = [['A', 'B'], ['C']]
    else:
        parts = [['A', 'B', 'C'], ['D', 'E'], ['F']]
    structure = BookStructure(parts=[Part(id=f'p{i}', arcs=[Arc(id=a) for a in part]) for i, part in enumerate(parts, 1)])
    flat = [a for part in parts for a in part]
    if kind == 'sequential':
        cuts = sorted(rng.sample(range(1, n), len(flat) - 1))
        arcs = [flat[sum(i >= c for c in cuts)] for i in range(n)]
    else:
        arcs = []
        for i in range(n):  # arcs move forward through the parts; sometimes a meeting scene of two arcs of one part
            part = parts[min(len(parts) - 1, i * len(parts) // n)]
            arcs.append(rng.sample(part, 2) if len(part) > 1 and rng.random() < 0.15 else rng.choice(part))
    scene_arcs = {s.id: a for s, a in zip(scenes, arcs)}
    if kind == 'outside':  # one active scene without a known arc moves the whole book to the chain
        scene_arcs[scenes[rng.randrange(n)].id] = rng.choice([None, 'Z'])
        scene_arcs = {k: v for k, v in scene_arcs.items() if v is not None}
    return Story(id='b', title='Книга', book_structure=structure, scene_arcs=scene_arcs), scenes


KINDS = ['none', 'one-arc', 'sequential', 'structured', 'outside']
CASES = [(kind, seed) for kind in KINDS for seed in range(40)]


def _check(story, scenes, parts):
    expected = reference_lineage_map(story, scenes)
    assert lineage_map(story, scenes) == expected
    for scene_id, item in expected.items():
        assert lineage(story, scenes, scene_id) == item
    outside = [Scene(id='unlisted', story_id='b', title='Нова', position=3), *[s for s in scenes if s.trashed_at]]
    for scene in [*scenes, *outside]:
        assert ([s.id for s in previous_scenes(story, scenes, scene)]
                == [s.id for s in reference_previous_scenes(story, scenes, scene)]), scene.id
    with pytest.raises(KeyError):
        lineage(story, scenes, 'unlisted')
    assert book_end_heads(story, scenes) == reference_book_end_heads(story, scenes)
    for part in parts:
        assert part_end_heads(story, scenes, part) == reference_part_end_heads(story, scenes, part)


@pytest.mark.parametrize('kind,seed', CASES)
def test_lineage_matches_reference(kind, seed):
    rng = random.Random(f'{kind}-{seed}')
    story, scenes = _book(kind, rng, rng.randrange(4, 14))
    parts = [p.id for p in story.book_structure.parts] if story.book_structure else []
    _check(story, scenes, parts)
    with lineage_scope():
        _check(story, scenes, parts)
        _check(story, scenes, parts)  # second pass reads the memo


def _counting(monkeypatch):
    calls = []
    original = module._build_map

    def counted(story, scenes):
        calls.append(1)
        return original(story, scenes)

    monkeypatch.setattr(module, '_build_map', counted)
    return calls


@pytest.mark.parametrize('kind', ['none', 'one-arc', 'outside'])
def test_chain_previous_scenes_builds_no_map(kind, monkeypatch):
    story, scenes = _book(kind, random.Random(kind), 12)
    calls = _counting(monkeypatch)
    for scene in scenes:
        assert ([s.id for s in previous_scenes(story, scenes, scene)]
                == [s.id for s in reference_previous_scenes(story, scenes, scene)])
    active = [s for s in scenes if not s.trashed_at]
    for s in active:
        assert lineage(story, scenes, s.id) == reference_lineage_map(story, scenes)[s.id]
    assert calls == []


@pytest.mark.parametrize('kind', ['sequential', 'structured'])
def test_structured_map_is_built_once_per_scope(kind, monkeypatch):
    story, scenes = _book(kind, random.Random(kind), 12)
    calls = _counting(monkeypatch)
    checks = []
    is_chain = module._is_chain
    monkeypatch.setattr(module, '_is_chain', lambda story, active: checks.append(1) or is_chain(story, active))
    with lineage_scope():
        with lineage_scope():  # a nested scope uses the outer memo
            for scene in scenes:
                previous_scenes(story, scenes, scene)
        book_end_heads(story, scenes)
    assert len(calls) == 1
    assert len(checks) <= 2  # the chain flag and the map build, not once per call
    calls.clear()
    for scene in scenes[:3]:  # outside a scope: no memory, as before
        previous_scenes(story, scenes, scene)
    assert len(calls) == 3


def test_scope_sees_a_structure_change_and_does_not_leak_mutation():
    story, scenes = _book('structured', random.Random('change'), 12)
    with lineage_scope():
        first = lineage_map(story, scenes)
        first.clear()  # a caller mutating its result does not spoil the memo
        assert lineage_map(story, scenes) == reference_lineage_map(story, scenes)
        # A binding change that changes the lineage (cross-review: the old one rebound a scene to its own arc).
        changed = next(c for c in (story.model_copy(update={'scene_arcs': {**story.scene_arcs, s.id: arc}})
                                   for s in scenes[1:4] for arc in 'ABC')
                       if reference_lineage_map(c, scenes) != reference_lineage_map(story, scenes))
        assert lineage_map(changed, scenes) == reference_lineage_map(changed, scenes)
        moved = [s.model_copy(update={'position': {1: 2, 2: 1}.get(s.position, s.position)}) for s in scenes]  # one part
        assert lineage_map(story, moved) == reference_lineage_map(story, moved)
        trashed = [scenes[0].model_copy(update={'trashed_at': '2026-11-21T10:00:00+00:00'}), *scenes[1:]]
        assert lineage_map(story, trashed) == reference_lineage_map(story, trashed)
    assert module._memo.get() is None


def test_story_request_builds_the_structured_map_at_most_once(tmp_path, monkeypatch):
    from tests.web.test_structure_api import put, setup
    client, repo, story, scenes = setup(tmp_path, n=6)
    assert put(client, story, scenes, ['a1', 'a2', 'a1', 'a2', 'b1', 'b1']).status_code == 200
    calls = _counting(monkeypatch)
    for url in (f'/api/stories/{story.id}', f'/api/stories/{story.id}/trash',
                f'/api/scenes/{scenes[4].id}/versions', f'/api/scenes/{scenes[4].id}/statistics?stage=draft',
                f'/api/stories/{story.id}/readiness?scene_id={scenes[4].id}'):
        calls.clear()
        assert client.get(url).status_code == 200, url
        assert len(calls) <= 1, (url, len(calls))
    assert module._memo.get() is None


def test_lineage_memo_does_not_outlive_a_request(tmp_path, monkeypatch):
    """Each request builds its own map: the second identical request builds it again (no cache between requests)."""
    from tests.web.test_structure_api import put, setup
    client, repo, story, scenes = setup(tmp_path, n=6)
    assert put(client, story, scenes, ['a1', 'a2', 'a1', 'a2', 'b1', 'b1']).status_code == 200
    calls = _counting(monkeypatch)
    url = f'/api/scenes/{scenes[4].id}/statistics?stage=draft'
    per_request = []
    for _ in range(2):
        calls.clear()
        assert client.get(url).status_code == 200
        per_request.append(len(calls))
    assert per_request == [1, 1]
