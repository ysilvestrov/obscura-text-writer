"""BOOK-LINEAGE-S03: an arc sees only its own stream until a merge; selection windows count lineage scenes."""
from storygen.generation.context import build_context
from storygen.memory.projection import MemoryItem
from storygen.memory.selection import SelectionInput, TIMELINE_WINDOW, select_memory
from storygen.providers.models import ProviderSettings, RoleSettings
from tests.memory.merge_helpers import arc_book

SETTINGS = RoleSettings(provider=ProviderSettings(model='test'))


def test_arc_b_sees_no_arc_a_memory(tmp_path):
    repo, story, scenes = arc_book(tmp_path, 'A B A B', [['A', 'B']])
    context = build_context(repo, scenes[3].id, 'brief', SETTINGS)
    assert 'Подія сцени 2' in context.user_text
    assert 'Подія сцени 1' not in context.user_text and 'Подія сцени 3' not in context.user_text
    foreign = {scenes[0].heads['prose'], scenes[2].heads['prose'], scenes[0].heads['memory'], scenes[2].heads['memory']}
    assert not foreign & set(context.input_refs)
    assert context.fragments['previous_prose_tail'].endswith('Сцена 2. Анна йде містом.')


def test_windows_count_lineage_scenes():
    # Scene 50 of the book is the 25th of its arc; a timeline entry of book scene 20 is its arc's 10th scene: 15 arc
    # scenes back — inside the window, though 30 book scenes back.
    item = MemoryItem(claim_id='t1', section='timeline', owner=None, line='— Подія', text='Подія', character_ids=(), slot=None, source_scene=20)
    ranks = {n: (n + 1) // 2 for n in range(2, 51, 2)}
    inp = SelectionInput(items=(item,), scene_id='s50', scene_number=50, cast=(), tracked=(), names={}, lineage_numbers=ranks)
    assert 50 - 20 > TIMELINE_WINDOW
    assert 't1' in select_memory(inp, 10000).selected_claim_ids
    flat = SelectionInput(items=(item,), scene_id='s50', scene_number=50, cast=(), tracked=(), names={})
    assert 't1' not in select_memory(flat, 10000).selected_claim_ids
