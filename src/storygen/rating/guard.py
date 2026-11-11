"""Minors safeguard checked before every generation request; raises author-facing ValueError."""
from ..characters.age import later_age_scenes, scene_ages
from ..characters.models import load_characters
from .. import build_edition
from .instructions import AXIS_NAMES
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
LATER='вік персонажа «{name}» указано лише у відомості, доступній від сцени {number} «{title}» (перевірте «Першу сцену доступності»)'
MORE='і ще {k}'
EDITION_LIMIT=('Генерацію заблоковано: рейтинг «{axis}» тут {n}, а в цьому виданні Obscura найвищий дозволений рівень — {max}. '
    'Знизьте рейтинг сцени або твору.')


def enforce_rating(view,story,scene,stage: str) -> None:
    """Order: unset story rating → build edition limit (every stage) → (scene stages, sexual ≥ 1) empty cast →
    no cards → participant ages."""
    if story.content_rating is None:raise ValueError(UNSET)
    # BUILD-EDITION-001: data rated above the edition limit (made in the full edition, imported, restored) is not
    # generated for; the author sees this cause before any cast or age check.
    rating=effective_rating(story,scene) if scene is not None else story.content_rating
    over=build_edition.over_limit(rating)
    if over:
        axis=over[0]
        raise ValueError(EDITION_LIMIT.format(axis=AXIS_NAMES[axis],n=getattr(rating,axis),max=getattr(build_edition.current().max_rating,axis)))
    if scene is None or stage not in SCENE_STAGES:return
    n=effective_rating(story,scene).sexual
    if n<1:return
    if not scene.character_ids:raise ValueError(EMPTY_CAST.format(n=n))
    if story.characters_version_id is None:raise ValueError(NO_CARDS.format(n=n))
    cards=load_characters(view.read_text(story.characters_version_id))
    names={card.id:card.name for card in cards}
    scenes=view.list_scenes(story.id)
    ages=scene_ages(cards,scenes,scene.id);later=later_age_scenes(cards,scenes,scene.id)
    def item(id,verdict):
        if verdict=='minor':return MINOR.format(name=names.get(id,id))
        # Scene numbers are 1-based in the interface (position + 1).
        if id in later:return LATER.format(name=names.get(id,id),number=later[id].position+1,title=later[id].title)
        return UNKNOWN.format(name=names.get(id,id))
    items=[item(id,verdict) for id,verdict in ages.items() if verdict!='adult']
    if not items:return
    listed=items[:MAX_LISTED]
    if len(items)>MAX_LISTED:listed.append(MORE.format(k=len(items)-MAX_LISTED))
    raise ValueError(PARTICIPANTS.format(n=n,items='; '.join(listed)))
