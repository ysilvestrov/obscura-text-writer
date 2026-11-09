"""Core state slots of tracked characters: registry and tracked-character selection. Pure, no IO."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlotDef:
    name: str
    label_uk: str
    label_en: str
    expires_on_day_change: bool


SLOT_REGISTRY_VERSION='core-slots-v1'
SLOTS=(
    SlotDef('clothing','одяг','clothing',True),
    SlotDef('carried','при собі','carried',True),
    SlotDef('location','місце','location',False),
    SlotDef('body','тілесний стан','body',True),
    SlotDef('company','з ким','company',False),
)


def slot_def(name):
    for slot in SLOTS:
        if slot.name==name:return slot
    raise KeyError(name)


def tracked_characters(cards,scenes):
    from ..characters.acquaintance import protagonist
    hero,_=protagonist(cards,[scene for scene in scenes if not scene.trashed_at])
    return [hero] if hero else []
