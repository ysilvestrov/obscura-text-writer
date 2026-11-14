"""SERIES integrity: series payloads, book references to an existing series and unique release numbers."""
from collections import Counter

from ..series_models import Series


def check_series(report, db, stories) -> None:
    known = {}
    if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='series'").fetchone():
        for id, revision, payload in db.execute('SELECT id,revision,payload FROM series'):
            try:
                item = Series.model_validate_json(payload)
                if item.id != id or item.revision != revision:
                    raise ValueError
                known[id] = item
            except ValueError:
                report.add('invalid_series', id, 'Некоректний запис серії')
    numbers = Counter()
    for story in stories.values():
        if story.series_id is None and story.series_number is None:
            continue
        if story.series_id not in known or story.series_number is None:
            report.add('invalid_series', story.id, 'Книга посилається на відсутню серію або не має номера')
            continue
        numbers[(story.series_id, story.series_number)] += 1
    for (series_id, number), count in numbers.items():
        if count > 1:
            report.add('invalid_series', series_id, f'Номер {number} у серії повторюється')
