"""R-52: operations of the MCP tool `update_characters` over the card list read from Obscura; pure, no IO.

The bridge applies them to the cards it has just read and sends the whole list to the same checks and save as the
Characters page, so the chat never has to repeat cards, entries or sources it does not change."""
import copy
import re

from ..characters.models import CharacterRecord
from ..characters.names import OTHER_NAMES, card_names, other_names_line, plain_line
from ..scene_description import name_key

OPERATIONS = {
    'add_character': ({'name'}, {'entries'}),
    'rename': ({'character_id', 'name'}, {'keep_old_name'}),
    'set_entry': ({'character_id'}, {'entry_id', 'text', 'availability', 'available_from_scene_id'}),
    'remove_entry': ({'character_id', 'entry_id'}, set()),
}
AVAILABILITY = ('unclassified', 'timeless', 'from_scene')
ENTRY_FIELDS = {'text', 'availability', 'available_from_scene_id'}
MAX_CHANGES = 100
OTHER_NAME_LABEL = {'uk': "Інше ім'я", 'en': 'Other name'}


class ChangeError(ValueError):
    """A change the bridge refuses before any request: the message names the change by its number."""


def _text(value, what: str, number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChangeError(f'Зміна {number}: {what} — непорожній рядок')
    return value.strip()


def _availability(entry: dict, change: dict, number: int) -> None:
    if 'availability' in change:
        if change['availability'] not in AVAILABILITY:
            raise ChangeError(f'Зміна {number}: availability — одне з {", ".join(AVAILABILITY)}')
        entry['availability'] = change['availability']
    if 'available_from_scene_id' in change:
        entry['available_from_scene_id'] = change['available_from_scene_id']
    if entry['availability'] != 'from_scene':
        entry['available_from_scene_id'] = None  # the model refuses a scene for any other availability
    elif not isinstance(entry.get('available_from_scene_id'), str) or not entry['available_from_scene_id']:
        raise ChangeError(f'Зміна {number}: для from_scene передайте available_from_scene_id (id сцени з get_characters)')


def _new_entry(change: dict, number: int) -> dict:
    entry = {'id': None, 'text': _text(change.get('text'), 'text', number), 'availability': 'unclassified',
             'available_from_scene_id': None, 'origin': 'author', 'sources': []}
    _availability(entry, change, number)
    return entry


def _card(cards: list[dict], change: dict, number: int) -> dict:
    card = next((card for card in cards if card.get('id') == change['character_id']), None)
    if card is None:
        raise ChangeError(f'Зміна {number}: немає картки {str(change["character_id"])[:80]!r} — візьміть id з get_characters')
    return card


def _entry(card: dict, change: dict, number: int) -> dict:
    entry = next((entry for entry in card['entries'] if entry.get('id') == change['entry_id']), None)
    if entry is None:
        raise ChangeError(f'Зміна {number}: у картці «{card["name"][:80]}» немає відомості {str(change["entry_id"])[:80]!r}')
    return entry


def _marker_prefix(line: str) -> str:
    """The line up to its colon, with the closing emphasis after it: «- **Інше ім'я:**» keeps its markup."""
    index = line.index(':') + 1
    closing = re.match(r'\*\*|__|\*|_', line[index:])
    return line[:index + (closing.end() if closing else 0)]


def keep_old_name(card: dict, old: str, language: str) -> None:
    """CHARACTER-NAMES: the old card name joins the first «Інше ім'я:» line of a timeless or unclassified entry, or a new
    timeless entry. A from_scene marker is left alone: it sets the name used from a scene on."""
    record = CharacterRecord.model_validate({**card, 'id': card.get('id') or 'new',
                                             'entries': [{**entry, 'id': entry.get('id') or f'new{i}'} for i, entry in enumerate(card['entries'])]})
    if name_key(old) in {name_key(name) for name in card_names(record)[1:]}:
        return
    for entry in card['entries']:
        if entry['availability'] == 'from_scene':
            continue
        lines = entry['text'].splitlines()
        for index, line in enumerate(lines):
            names = other_names_line(line)
            if names is None or not OTHER_NAMES.match(plain_line(line)):
                continue
            lines[index] = f'{_marker_prefix(line)} {", ".join([*names, old])}'
            entry['text'] = '\n'.join(lines)
            entry['origin'] = 'author'
            return
    label = OTHER_NAME_LABEL.get(language, OTHER_NAME_LABEL['en'])
    card['entries'].append({'id': None, 'text': f'{label}: {old}', 'availability': 'timeless', 'available_from_scene_id': None,
                            'origin': 'author', 'sources': []})


def apply_changes(cards: list[dict], changes: list, language: str) -> list[dict]:
    """The new card list; the input is not modified. Entries created or changed by an operation get origin «author»."""
    if not isinstance(changes, list) or not changes:
        raise ChangeError('Передайте хоча б одну зміну (changes)')
    if len(changes) > MAX_CHANGES:
        raise ChangeError(f'Не більше {MAX_CHANGES} змін за виклик')
    result = copy.deepcopy(cards)
    for number, change in enumerate(changes, 1):
        if not isinstance(change, dict) or change.get('op') not in OPERATIONS:
            raise ChangeError(f'Зміна {number}: op — одна з {", ".join(OPERATIONS)}')
        required, optional = OPERATIONS[change['op']]
        fields = set(change) - {'op'}
        missing, unknown = sorted(required - fields), sorted(fields - required - optional)
        if missing or unknown:
            raise ChangeError(f'Зміна {number} ({change["op"]}): ' + ('бракує ' + ', '.join(missing) if missing else 'зайві поля ' + ', '.join(unknown)))
        op = change['op']
        if op == 'add_character':
            entries = change.get('entries') or []
            if not isinstance(entries, list) or any(not isinstance(e, dict) or set(e) - ENTRY_FIELDS for e in entries):
                raise ChangeError(f'Зміна {number}: entries — список {{text, availability?, available_from_scene_id?}}')
            result.append({'id': None, 'name': _text(change['name'], 'name', number),
                           'entries': [_new_entry(entry, number) for entry in entries]})
            continue
        card = _card(result, change, number)
        if op == 'rename':
            old, new = card['name'], _text(change['name'], 'name', number)
            card['name'] = new
            if change.get('keep_old_name', True) and name_key(old) != name_key(new):
                keep_old_name(card, old, language)
        elif op == 'set_entry':
            if change.get('entry_id') is None:
                card['entries'].append(_new_entry(change, number))
                continue
            entry = _entry(card, change, number)
            if not ENTRY_FIELDS & fields:
                raise ChangeError(f'Зміна {number}: передайте text, availability або available_from_scene_id')
            if 'text' in change:
                entry['text'] = _text(change['text'], 'text', number)
            _availability(entry, change, number)
            entry['origin'] = 'author'
        else:
            card['entries'].remove(_entry(card, change, number))
    return result


def describe(before: list[dict], after: list[dict]) -> list[dict]:
    """What the author is shown: per card, the name was → is and the entries added, changed (text was → is) or removed."""
    old = {card['id']: card for card in before}
    shown = []
    for card in after:
        previous = old.get(card.get('id'))
        if previous is None:
            shown.append({'character_id': None, 'name': card['name'], 'added': True,
                          'entries_added': [entry['text'] for entry in card['entries']]})
            continue
        entries = {entry['id']: entry for entry in previous['entries']}
        kept = {entry.get('id') for entry in card['entries']}
        item = {'character_id': card['id'], 'name': card['name']}
        if previous['name'] != card['name']:
            item['name_was'] = previous['name']
        added = [entry['text'] for entry in card['entries'] if entry.get('id') is None]
        changed = [{'entry_id': entry['id'], 'text_was': entries[entry['id']]['text'], 'text': entry['text'],
                    'availability': entry['availability'], 'available_from_scene_id': entry['available_from_scene_id']}
                   for entry in card['entries'] if entry.get('id') in entries and entry != entries[entry['id']]]
        removed = [{'entry_id': id, 'text': entry['text']} for id, entry in entries.items() if id not in kept]
        for key, value in (('entries_added', added), ('entries_changed', changed), ('entries_removed', removed)):
            if value:
                item[key] = value
        if len(item) > 2:
            shown.append(item)
    return shown
