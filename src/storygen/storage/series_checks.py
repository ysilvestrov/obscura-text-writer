"""SERIES integrity: series payloads, book references to an existing series, unique release numbers and the start
snapshot of a book (a series_start version of the same book). A world bible (SERIES-BIBLE-001) belongs to a known series
without a number, a start or a start snapshot, and a series has at most one, the trash included."""
from collections import Counter

from ..series_models import Series


def check_series(report, db, stories, versions=None) -> None:
    known = {}
    if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='series'").fetchone():
        for id, revision, payload in db.execute('SELECT id,revision,payload FROM series'):
            try:
                item = Series.model_validate_json(payload)
                if item.id != id or item.revision != revision:
                    raise ValueError
                known[id] = item
            except ValueError:
                report.add('invalid_series', id, 'Invalid series record')
    numbers, bibles = Counter(), Counter()
    for story in stories.values():
        if story.series_bible:
            if story.series_id not in known:
                report.add('invalid_series', story.id, 'The world bible refers to a missing series')
            elif story.series_number is not None or story.series_start is not None or story.series_start_version_id:
                report.add('invalid_series', story.id, 'The world bible has a number, a start or a start snapshot')
            else:
                bibles[story.series_id] += 1
            continue
        if story.series_id is None and story.series_number is None:
            if story.series_start_version_id:  # leaving a series clears it
                report.add('invalid_series', story.id, 'Series start snapshot in a book outside the series')
            elif story.series_start is not None:
                report.add('invalid_series', story.id, 'Series start in a book outside the series')
            continue
        if story.series_id not in known or story.series_number is None:
            report.add('invalid_series', story.id, 'The book refers to a missing series or has no number')
            continue
        numbers[(story.series_id, story.series_number)] += 1
        start = (versions or {}).get(story.series_start_version_id) if story.series_start_version_id else None
        if story.series_start_version_id and versions is not None and (
                start is None or start.kind != 'series_start' or start.story_id != story.id):
            report.add('invalid_series', story.id, 'The series start snapshot is not a snapshot of this book')
    for (series_id, number), count in numbers.items():
        if count > 1:
            report.add('invalid_series', series_id, f'Number {number} is repeated in the series')
    for series_id, count in bibles.items():
        if count > 1:
            report.add('invalid_series', series_id, 'The series has more than one world bible')
