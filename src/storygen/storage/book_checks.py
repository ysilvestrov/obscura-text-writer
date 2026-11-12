"""BOOK-STRUCTURE fsck: a broken structure is a limitation, not an issue — no context or version depends on it."""
from ..book.structure import arc_order, check_sequential


def check_book_structure(report, stories, scenes):
    for story in stories.values():
        if story.book_structure is None:
            continue
        active = [s for s in scenes.values() if s.story_id == story.id and not s.trashed_at]
        known = arc_order(story.book_structure)
        unknown = [s for s in active if s.id in story.scene_arcs and story.scene_arcs[s.id] not in known]
        if unknown:
            report.limitations.append(f'{story.id}: book_structure_unknown_arc: {len(unknown)} сцен прив’язано до арок, яких немає; '
                                      'збережіть структуру книги заново.')
        if check_sequential(story.book_structure, story.scene_arcs, active):
            report.limitations.append(f'{story.id}: book_structure_not_sequential: арки чи частини книги перемішані або сцена без арки; '
                                      'виправте структуру в налаштуваннях твору.')
