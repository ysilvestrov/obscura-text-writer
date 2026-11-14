"""SERIES-S10: the future of a prequel — records of later books the prequel must not contradict, as lines of the writing
requests. Read from the prequel's start snapshot (`future`); they are not memory and carry no quotes."""
from .selection import mentions, name_stems

CATEGORY_ORDER = ('character_states', 'facts', 'open_threads', 'timeline')


def future_lines(future: list[dict], cast: set[str], names: dict[str, str], limit: int) -> tuple[list[str], int]:
    """Lines for a scene and the number of records left out by `limit` (characters): first the states of the scene's
    heroes, then facts and threads about or mentioning them, then records without heroes; records only about heroes
    outside the scene are not for this scene. Within a group by category, then text."""
    stems = tuple(stem for id in cast for stem in name_stems(names.get(id, '')))

    def group(item):
        heroes = set(item['character_ids'])
        if heroes & cast:
            return 0 if item['category'] == 'character_states' else 1
        if stems and mentions(item['text'], stems):
            return 1
        return 2 if not heroes else None
    order = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    chosen = sorted(((group(item), order.get(item['category'], len(order)), item['text'], item) for item in future
                     if group(item) is not None), key=lambda row: row[:3])
    lines, used = [], 0
    for n, (*_, item) in enumerate(chosen):
        who = ', '.join(names.get(id, id) for id in item['character_ids'])
        line = f"- {who}: {item['text']}" if who else f"- {item['text']}"
        if used + len(line) + 1 > limit:
            return lines, len(chosen) - n
        lines.append(line)
        used += len(line) + 1
    return lines, 0


def future_block(reader, story, scene, limit: int) -> tuple[list[str], int]:
    """(lines, records left out) of a scene of a book whose start snapshot has a future; ([], 0) otherwise."""
    from ..characters.models import load_characters
    from .series_start import read_series_start
    if not story.series_start_version_id:
        return [], 0
    future = read_series_start(reader.read_text(story.series_start_version_id), story.series_start_version_id).future
    if not future:
        return [], 0
    cards = load_characters(reader.read_text(story.characters_version_id)) if story.characters_version_id else []
    return future_lines(future, set(scene.character_ids), {card.id: card.name for card in cards}, limit)


def future_section(reader, story, scene, language: str, limit: int) -> str | None:
    """The future section of a writing request, or None when there is nothing to show."""
    from ..generation.context_labels import label
    lines, dropped = future_block(reader, story, scene, limit)
    if not lines and not dropped:
        return None
    note = [label('future_more', language, count=dropped)] if dropped else []
    return '\n'.join([label('future_facts', language), *lines, *note])


def future_value(reader, story) -> list | None:
    """The dependency value of the future section: «key|text» of every future record (a selector holds a flat list of
    strings), None without one."""
    from .series_start import read_series_start
    if not story.series_start_version_id:
        return None
    future = read_series_start(reader.read_text(story.series_start_version_id), story.series_start_version_id).future
    return [f"{item['key']}|{item['text']}" for item in future] or None
