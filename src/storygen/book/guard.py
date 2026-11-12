"""Long prose is a build tier (BUILD-EDITION-001): an edition without it refuses to edit a book structure."""
from .. import build_edition

NO_LONG_PROSE = 'Частини й арки доступні лише у виданні з довгою прозою'


def require_long_prose() -> None:
    if not build_edition.current().long_prose:
        raise ValueError(NO_LONG_PROSE)
