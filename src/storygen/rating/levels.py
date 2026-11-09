from ..domain import ContentRating, Scene, Story

AXES=('sexual','violence','themes')


def effective_rating(story: Story,scene: Scene) -> ContentRating | None:
    return scene.content_rating or story.content_rating


def is_lower(current: ContentRating | None,expected: ContentRating | None) -> bool:
    if current is None or expected is None:return False
    return any(getattr(current,a)<getattr(expected,a) for a in AXES)


def to_wire(r: ContentRating | None) -> list[str] | None:
    return None if r is None else [str(getattr(r,a)) for a in AXES]


def from_wire(v: list[str] | None) -> ContentRating | None:
    if v is None:return None
    if len(v)!=len(AXES):raise ValueError('Невірний формат рейтингу')
    return ContentRating(**{a:int(x) for a,x in zip(AXES,v)})


def higher_axes(other: ContentRating,base: ContentRating) -> list[str]:
    return [a for a in AXES if getattr(other,a)>getattr(base,a)]
