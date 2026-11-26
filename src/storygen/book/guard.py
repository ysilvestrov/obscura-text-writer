"""Long prose is a build tier (BUILD-EDITION-001): an edition without it refuses to edit a book structure, and opens a
book with several parts or arcs for reading and export only."""
from .. import build_edition

NO_LONG_PROSE = 'Частини й арки доступні лише у виданні з довгою прозою'
READ_ONLY = 'Ця книга має частини чи арки; у цій збірці вона доступна лише для читання й експорту'
# SERIES-S06: a book of a series is long prose too.
READ_ONLY_SERIES = 'Ця книга входить у серію; у цій збірці вона доступна лише для читання й експорту'
# LONG-PROSE-TRIAL (R-47): refusals of the trial; the edition ones reach the chat with the paid-version hint (mcp/edition.py).
TRIAL_USED = 'Пробу довгої прози вже використано; інші книги з частинами й серії — у платній версії'
TRIAL_SERIES_FULL = 'Проба серії дозволяє дві книги; третя — у платній версії'
TRIAL_IN_SERIES = 'Ця книга входить у серію; оберіть пробою серію'
TRIAL_CONFIRM = 'Проба одна на всі твори: підтвердьте вибір книги чи серії'
TRIAL_NOT_NEEDED = 'Довга проза вже є в цій збірці'
TRIAL_BOOK_ALONE = 'Пробна книга не входить у серію: проба одна'
TRIAL_BIBLE_USED = 'Проба серії має одну біблію світу; інша — у платній версії'


def require_long_prose() -> None:
    if not build_edition.current().long_prose:
        raise ValueError(NO_LONG_PROSE)


# R-47: the checks ask about a book or a series. An edition with long prose never reads the database here; one without
# it answers yes only for the trial (LONG-PROSE-TRIAL): its book, the listed books of its series and its remembered bible.
def _covered(item, story) -> bool:
    from ..storage.long_prose_trial import covers
    return covers(item, story.id)


def long_prose_for(repo, story) -> bool:
    if build_edition.current().long_prose:
        return True
    from ..storage.long_prose_trial import trial
    return _covered(trial(repo), story)


def story_long_prose(repo, story_id: str) -> bool:
    """False for an unknown story in an edition without long prose."""
    if build_edition.current().long_prose:
        return True
    try:
        story = repo.get_story(story_id, include_trashed=True)
    except KeyError:
        return False
    return long_prose_for(repo, story)


def series_long_prose(repo, series_id: str) -> bool:
    if build_edition.current().long_prose:
        return True
    from ..storage.long_prose_trial import trial
    item = trial(repo)
    return item is not None and item.kind == 'series' and item.id == series_id


def require_long_prose_for(repo, story_id: str) -> None:
    if not story_long_prose(repo, story_id):
        raise ValueError(NO_LONG_PROSE)


def require_series_long_prose(repo, series_id: str) -> None:
    if not series_long_prose(repo, series_id):
        raise ValueError(NO_LONG_PROSE)


def enforce_long_prose(story, scenes) -> None:
    from .structure import structure_kind
    if not build_edition.current().long_prose and structure_kind(story, scenes) == 'structured':
        raise ValueError(READ_ONLY)
