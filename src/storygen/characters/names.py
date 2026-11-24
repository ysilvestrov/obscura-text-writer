"""CHARACTER-NAMES (#215): other names of a card from «Інше ім'я:» lines and the name current in a scene; pure, no IO."""
import re
from ..scene_description import split_participants, name_key

OTHER_NAMES = re.compile(r"(?i)^(?:інше\s+ім['’ʼ]я|інші\s+імена|також\s+відом(?:ий|а|і)\s+як|other\s+names?|also\s+known\s+as|aka)\s*:\s*(.*)$")
AMBIGUOUS_NAME_WARNING = 'Ім’я «{name}» мають кілька карток: {cards}; у плані воно не розпізнається.'
SHADOWED_NAME_WARNING = 'Ім’я «{name}» є основним ім’ям картки «{card}» та іншим ім’ям карток: {others}; у плані воно означає основну картку.'


def plain_line(line):
    return re.sub(r'^[\s\-—–]+', '', line.replace('**', '').replace('__', '').replace('*', '').strip()).strip()


def other_names_line(line):
    match = OTHER_NAMES.match(plain_line(line))
    if not match:
        return None
    # A placeholder such as «—» names nobody: only entries with a letter or digit are names.
    return [name for name in split_participants(match.group(1)) if any(char.isalnum() for char in name)]


def _entry_names(entry):
    return [name for line in entry.text.splitlines() for name in (other_names_line(line) or [])]


def _unique(names):
    seen, result = set(), []
    for name in names:
        if name_key(name) not in seen:
            seen.add(name_key(name)); result.append(name)
    return result


def card_names(card):
    """The card name and every name of its marker lines, whatever their scene: all of them resolve in a plan."""
    return _unique([card.name] + [name for entry in getattr(card, 'entries', ()) for name in _entry_names(entry)])


def _candidates(cards):
    """{name_key: ([ids with it as the card name], [ids with it only as an other name])}."""
    index = {}
    for card in cards:
        for position, name in enumerate(card_names(card)):
            index.setdefault(name_key(name), ([], []))[position > 0].append(card.id)
    return index


def name_index(cards):
    """{name_key: [card ids]}; one id means the name resolves. The card name wins over other names of other cards:
    only two card names, or two other names without a card name, stay ambiguous."""
    return {key: primary if primary else others for key, (primary, others) in _candidates(cards).items()}


def scene_name(card, active, scene):
    """(current, earlier): the first name of the available from_scene marker with the latest anchor, else the card name;
    earlier names are the card name and the other available marker names. Unavailable entries give no names."""
    from .projection import entry_available
    best, available = None, []
    for entry in card.entries:
        names = _entry_names(entry)
        if not names or not entry_available(entry, active, scene):
            continue
        available.extend(names)
        if entry.availability == 'from_scene':
            position = active[entry.available_from_scene_id].position
            if best is None or position > best[0]:
                best = (position, names[0])
    current = best[1] if best else card.name
    return current, [name for name in _unique([card.name] + available) if name_key(name) != name_key(current)]


def _active(scenes):
    return {scene.id: scene for scene in scenes if not scene.trashed_at}


def scene_names(cards, scenes, scene):
    """Names shown to a model in a request for the scene."""
    active = _active(scenes)
    return {card.id: scene_name(card, active, scene)[0] for card in cards}


def scene_match_names(cards, scenes, scene):
    """Every name available in the scene, for finding mentions in memory text; equals the card name without markers."""
    active = _active(scenes)
    return {card.id: ', '.join([current, *earlier]) for card in cards for current, earlier in [scene_name(card, active, scene)]}


def name_warnings(cards):
    by_id = {card.id: card.name for card in cards}
    warnings, shown = [], {}
    for card in cards:
        for name in card_names(card):
            shown.setdefault(name_key(name), name)
    label = lambda ids: ', '.join(by_id[id][:120] for id in ids)
    for key, (primary, others) in _candidates(cards).items():
        ids = primary or others
        if len(ids) > 1:
            warnings.append(AMBIGUOUS_NAME_WARNING.format(name=shown[key][:120], cards=label(ids)))
        elif primary and others:
            warnings.append(SHADOWED_NAME_WARNING.format(name=shown[key][:120], card=by_id[primary[0]][:120], others=label(others)))
    return warnings
