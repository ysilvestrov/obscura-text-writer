"""BOOK-LINEAGE-S04: the acquaintance hero of a scene is the protagonist of its arc; a flat book keeps the book hero."""
import threading

from storygen.characters.acquaintance import acquaintance_material
from storygen.characters.brief_link import brief_link_state
from storygen.generation.context import build_context
from storygen.generation.models import WritersBrief
from storygen.storage.book_structure import put_structure
from tests.generation.test_acquaintance_context import prepared, settings

HEADER = 'ЗНАЙОМСТВА ГОЛОВНОГО ГЕРОЯ — '


def arcs_story(tmp_path):
    """Scene 1 in arc X (book hero Анна), scene 2 in arc Y with protagonist Богдан; Анна is in both casts."""
    repo, story, (first, second) = prepared(tmp_path, [['A', 'B'], ['A', 'B', 'C']], {'A': 'Протагоністка'})
    parts = [{'id': 'p1', 'title': '', 'arcs': [{'id': 'X', 'title': ''}]},
             {'id': 'p2', 'title': '', 'arcs': [{'id': 'Y', 'title': '', 'protagonist_id': 'B'}]}]
    put_structure(repo, story.id, parts, {first.id: 'X', second.id: 'Y'}, repo.get_story(story.id).revision)
    return repo, story, first, second


def block(repo, story, scene, stage='brief'):
    view = repo.context_view(story.id)
    return acquaintance_material(view, view.get_story(story.id), view.get_scene(scene.id), stage)[0]


def test_acquaintance_block_names_the_arc_protagonist(tmp_path):
    repo, story, first, second = arcs_story(tmp_path)
    text = block(repo, story, second)
    assert text.startswith(HEADER + 'Богдан')
    assert 'Анна [id=A]' in text and 'Віра [id=C]' in text
    assert block(repo, story, first).startswith(HEADER + 'Анна')


def test_flat_book_acquaintance_is_unchanged(tmp_path):
    repo, story, (first, second) = prepared(tmp_path, [['A', 'B'], ['A', 'B', 'C']], {'A': 'Протагоністка'})
    assert block(repo, story, second).startswith(HEADER + 'Анна')
    assert 'Богдан [id=B]' in block(repo, story, second)


def test_brief_link_state_uses_the_scene_hero(tmp_path):
    repo, story, first, second = arcs_story(tmp_path)
    view = repo.context_view(story.id)
    current = view.get_story(story.id)
    late = brief_link_state(view, current, view.get_scene(second.id))
    assert late['hero_id'] == 'B' and late['hero_name'] == 'Богдан'
    assert [row['id'] for row in late['cast']] == ['A', 'C']
    assert brief_link_state(view, current, view.get_scene(first.id))['hero_id'] == 'A'


def test_planner_warning_uses_the_scene_hero(tmp_path):
    # Анна is an ordinary cast member in arc Y, so a brief may introduce her there.
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    # The arc-Y scene comes first: a brief of a later scene would need the previous scene's memory.
    repo, story, (second,) = prepared(tmp_path, [['A', 'B', 'C']], {'A': 'Протагоністка'})
    parts = [{'id': 'p1', 'title': '', 'arcs': [{'id': 'Y', 'title': '', 'protagonist_id': 'B'}]}]
    put_structure(repo, story.id, parts, {second.id: 'Y'}, repo.get_story(story.id).revision)
    ctx = build_context(repo, second.id, 'brief', settings('brief'))
    body = WritersBrief(objective='o', beats=['b'], introduced=['A']).model_dump_json()

    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=body)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, second.id, 'brief', ctx, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    assert attempt.context['planner_warnings'] == []
