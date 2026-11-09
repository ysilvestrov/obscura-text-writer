"""Minors safeguard checked before every generation request; raises author-facing ValueError."""
from ..characters.age import scene_ages
from ..characters.models import load_characters
from .levels import effective_rating

SCENE_STAGES=frozenset({'brief','draft','edit','rewrite','memory'})
MAX_LISTED=5

UNSET='Задайте віковий рейтинг твору в налаштуваннях, щоб запустити генерацію.'
EMPTY_CAST='Сцена має рейтинг сексуального змісту {n}, але склад сцени порожній. Укажіть учасників, щоб перевірити їхній вік.'
NO_CARDS='Сцена має рейтинг сексуального змісту {n}. Підготуйте картки персонажів із рядком «Вік:», щоб перевірити вік учасників.'
PARTICIPANTS=('Генерацію заблоковано: сцена має рейтинг сексуального змісту {n}, а {items}. Допишіть у картку рядок «Вік: …» '
    '(число від 18 або «дорослий»), приберіть персонажа зі складу сцени або позначте сцену рейтингом «сексуальний зміст 0».')
MINOR='персонаж «{name}» молодший за 18'
UNKNOWN='персонаж «{name}» не має вказаного віку'
MORE='і ще {k}'


def enforce_rating(view,story,scene,stage: str) -> None:
    """Order: unset story rating → (scene stages, sexual ≥ 1) empty cast → no cards → participant ages."""
    if story.content_rating is None:raise ValueError(UNSET)
    if scene is None or stage not in SCENE_STAGES:return
    n=effective_rating(story,scene).sexual
    if n<1:return
    if not scene.character_ids:raise ValueError(EMPTY_CAST.format(n=n))
    if story.characters_version_id is None:raise ValueError(NO_CARDS.format(n=n))
    cards=load_characters(view.read_text(story.characters_version_id))
    names={card.id:card.name for card in cards}
    ages=scene_ages(cards,view.list_scenes(story.id),scene.id)
    items=[(MINOR if verdict=='minor' else UNKNOWN).format(name=names.get(id,id)) for id,verdict in ages.items() if verdict!='adult']
    if not items:return
    listed=items[:MAX_LISTED]
    if len(items)>MAX_LISTED:listed.append(MORE.format(k=len(items)-MAX_LISTED))
    raise ValueError(PARTICIPANTS.format(n=n,items='; '.join(listed)))
