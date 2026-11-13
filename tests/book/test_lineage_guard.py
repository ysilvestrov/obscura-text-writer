"""BOOK-LINEAGE-S01/S03: memory, context and dependencies take earlier scenes from the lineage, not from positions."""
import re
from pathlib import Path

from storygen.domain import Arc, BookStructure, Part, StoryCreate, SceneCreate
from storygen.storage.repository import Repository

SRC = Path(__file__).resolve().parents[2] / 'src/storygen'
PREFIX = re.compile(r'\.position\s*<=?\s*\w+\.position')
# Reading order on purpose (spec «Родовід»): the book is evaluated, rated, its cards revealed, its impact checked and its
# brief inputs listed as written. A single line elsewhere opts out with the comment `# reading order`.
EXCEPTIONS = {'book/lineage.py', 'evaluation/story_adapter.py', 'rating/instructions.py', 'web/routes_versions.py',
              'characters/age.py', 'characters/projection.py', 'impact/memory_review.py', 'impact/planning.py'}


def test_no_position_prefix_outside_lineage():
    found = sorted(f'{path.relative_to(SRC).as_posix()}:{n}' for path in SRC.rglob('*.py')
                   for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
                   if PREFIX.search(line) and '# reading order' not in line and path.relative_to(SRC).as_posix() not in EXCEPTIONS)
    assert found == []


def test_snapshot_order_of_an_interleaved_book_follows_the_lineage(tmp_path):
    from storygen.storage.snapshots import selector_value
    from storygen.dependency_models import DependencySelector
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats='Іде.')) for n in range(1, 5)]
    # A B A B, built directly: the structure check of this PR still refuses interleaving on save.
    structure = BookStructure(parts=[Part(id='p1', arcs=[Arc(id='A'), Arc(id='B')])])
    arcs = dict(zip([s.id for s in scenes], 'ABAB'))
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = repo._active_story(db, story.id)
        repo._save_story(db, current.model_copy(update={'book_structure': structure, 'scene_arcs': arcs}))
    view = repo.context_view(story.id)
    prefix = selector_value(view, DependencySelector(kind='order', owner_id=scenes[3].id, field='prefix', expected=[]))
    assert prefix == [scenes[1].id, scenes[3].id]
    window = selector_value(view, DependencySelector(kind='order', owner_id=scenes[2].id, field='narrative_window', expected=[],
                                                     future_count=1))
    assert window == [scenes[0].id, scenes[2].id, scenes[3].id]  # lineage of A2, then A2 and one scene ahead
