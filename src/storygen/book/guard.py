"""Long prose is a build tier (BUILD-EDITION-001): an edition without it refuses to edit a book structure, and opens a
book with several parts or arcs for reading and export only."""
from .. import build_edition

NO_LONG_PROSE = 'Частини й арки доступні лише у виданні з довгою прозою'
READ_ONLY = 'Ця книга має частини чи арки; у цій збірці вона доступна лише для читання й експорту'


def require_long_prose() -> None:
    if not build_edition.current().long_prose:
        raise ValueError(NO_LONG_PROSE)


def enforce_long_prose(story, scenes) -> None:
    from .structure import structure_kind
    if not build_edition.current().long_prose and structure_kind(story, scenes) == 'structured':
        raise ValueError(READ_ONLY)
