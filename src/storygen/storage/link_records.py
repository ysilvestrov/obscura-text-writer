"""VALID-LINKS: append-only verdicts on the three links of a scene, kept in app_settings without a migration.

A verdict holds for the link's fingerprint at the time it was written; a changed component changes the fingerprint and
the verdict stops applying. The last record for (scene, link, fingerprint) wins. "Last" is insertion order (rowid)."""
from typing import Literal
from pydantic import Field, model_validator
from ..dependency_models import DependencyModel
from ..domain import new_id

LinkName = Literal['brief', 'prose', 'memory']
LINKS: tuple[LinkName, ...] = ('brief', 'prose', 'memory')
PREFIX = 'link_verdict:'


class Discrepancy(DependencyModel):
    text: str = Field(min_length=1, max_length=2000)
    quote: str | None = Field(default=None, max_length=2000)


class LinkVerdict(DependencyModel):
    id: str = Field(min_length=1, max_length=64)
    story_id: str
    scene_id: str
    link: LinkName
    inputs: dict[str, str | None]
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    source: Literal['auditor', 'author']
    outcome: Literal['valid', 'discrepancy', 'unavailable']
    confidence: int | None = Field(default=None, ge=0, le=100)
    discrepancies: list[Discrepancy] = Field(default_factory=list, max_length=20)
    reason: str | None = Field(default=None, max_length=2000)
    attempt_id: str | None = None
    run_id: str | None = None
    created_at: str


def new_verdict_id() -> str:
    return new_id()


def verdict_key(story_id: str, verdict_id: str) -> str:
    return PREFIX + story_id + ':' + verdict_id


def write_verdict(db, verdict: LinkVerdict) -> None:
    """Inside the caller's transaction."""
    db.execute('INSERT INTO app_settings VALUES(?,?)', (verdict_key(verdict.story_id, verdict.id), verdict.model_dump_json()))


def load_verdicts(db, story_id: str, scenes, order: dict | None = None) -> dict[tuple[str, str, str], LinkVerdict]:
    """{(scene_id, link, fingerprint): last verdict}; `order` receives {verdict id: rowid}, the insertion order rule (г)
    compares with invalidations (created_at may tie). A record under a foreign key or for a foreign scene is damage."""
    verdicts = {}
    for rowid, key, payload in db.execute('SELECT rowid,key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',
                                          (PREFIX + story_id + ':%',)):
        record = LinkVerdict.model_validate_json(payload)
        scene = scenes.get(record.scene_id)
        if record.story_id != story_id or key != verdict_key(story_id, record.id) or scene is None or scene.story_id != story_id:
            raise ValueError('Пошкоджений журнал висновків про зв’язки')
        verdicts[(record.scene_id, record.link, record.fingerprint)] = record
        if order is not None:
            order[record.id] = rowid
    return verdicts


def check_verdicts(db, scenes, report) -> None:
    """fsck: key shape, model and scene ownership of every verdict."""
    for key, payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'link_verdict:%' ORDER BY rowid"):
        try:
            record = LinkVerdict.model_validate_json(payload)
            scene = scenes.get(record.scene_id)
            if key != verdict_key(record.story_id, record.id) or scene is None or scene.story_id != record.story_id:
                raise ValueError('Invalid record')
        except (ValueError, TypeError):
            report.add('invalid_link_verdict', key, 'Invalid format or ownership of a link verdict')


EQUIVALENCE_PREFIX = 'prose_equivalence:'
PROSE_KINDS = {'manual', 'edited'}


class ProseEquivalence(DependencyModel):
    """Z3 kept by the auditor or the author after a prose change: the old prose (the one later journals cite) and the
    new head are equivalent for the memory of this scene."""
    id: str = Field(min_length=1, max_length=64)
    story_id: str
    scene_id: str
    old_prose_id: str
    new_prose_id: str
    verdict_id: str
    created_at: str


def equivalence_key(story_id: str, record_id: str) -> str:
    return EQUIVALENCE_PREFIX + story_id + ':' + record_id


def write_equivalence(db, record: ProseEquivalence) -> None:
    """Inside the caller's transaction."""
    db.execute('INSERT INTO app_settings VALUES(?,?)', (equivalence_key(record.story_id, record.id), record.model_dump_json()))


def _equivalence_ok(key, record, scenes, versions) -> bool:
    scene = scenes.get(record.scene_id)
    return (key == equivalence_key(record.story_id, record.id) and scene is not None and scene.story_id == record.story_id
            and all(id in versions and versions[id].scene_id == record.scene_id and versions[id].kind in PROSE_KINDS
                    for id in (record.old_prose_id, record.new_prose_id)))


def load_equivalences(db, story_id: str, scenes, versions) -> list[ProseEquivalence]:
    """Records of the story in write order; a foreign key, scene or prose version is damage."""
    records = []
    for key, payload in db.execute('SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',
                                   (EQUIVALENCE_PREFIX + story_id + ':%',)):
        record = ProseEquivalence.model_validate_json(payload)
        if record.story_id != story_id or not _equivalence_ok(key, record, scenes, versions):
            raise ValueError('Пошкоджений журнал рівноцінності прози')
        records.append(record)
    return records


def equivalent_pairs(view, scene_id: str) -> set[tuple[str, str]]:
    """Directed transitive closure of the scene's (old, new) prose pairs. A Repository caller (execute_stage) reads them
    through a context view of the scene's story."""
    records = getattr(view, 'prose_equivalences', None)
    if records is None:
        records = view.context_view(view.get_scene(scene_id).story_id).prose_equivalences
    edges = {}
    for record in records:
        if record.scene_id == scene_id and record.old_prose_id != record.new_prose_id:
            edges.setdefault(record.old_prose_id, set()).add(record.new_prose_id)
    pairs = set()
    for start in edges:
        stack, seen = list(edges[start]), set()
        while stack:
            node = stack.pop()
            if node not in seen:
                seen.add(node)
                stack.extend(edges.get(node, ()))
        pairs.update((start, node) for node in seen if node != start)
    return pairs


def check_equivalences(db, scenes, versions, report) -> None:
    """fsck: key shape, model, scene ownership and prose versions of every equivalence."""
    for key, payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'prose_equivalence:%' ORDER BY rowid"):
        try:
            if not _equivalence_ok(key, ProseEquivalence.model_validate_json(payload), scenes, versions):
                raise ValueError('Invalid record')
        except (ValueError, TypeError):
            report.add('invalid_prose_equivalence', key, 'Invalid format or ownership of a prose equivalence')


INVALIDATION_PREFIX = 'link_invalidation:'
CARD_LINKS = ('brief', 'prose')


class InvalidationReason(DependencyModel):
    kind: Literal['character', 'location']
    ids: list[str] = Field(min_length=1, max_length=1000)


class LinkInvalidation(DependencyModel):
    """The author's «Так» after a card or location change: Z1/Z2 of the scene with these fingerprints lose construction,
    auditor and author validity until a later valid verdict (rule (г)); a changed fingerprint makes it inert."""
    id: str = Field(min_length=1, max_length=64)
    story_id: str
    scene_id: str
    links: list[Literal['brief', 'prose']] = Field(min_length=1, max_length=2)
    fingerprints: dict[str, str]
    reason: InvalidationReason
    created_at: str

    @model_validator(mode='after')
    def fingerprints_match_links(self):
        if len(set(self.links)) != len(self.links) or set(self.fingerprints) != set(self.links) or not all(
                isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
                for value in self.fingerprints.values()):
            raise ValueError('Відбитки інвалідації не відповідають зв’язкам')
        return self


def invalidation_key(story_id: str, record_id: str) -> str:
    return INVALIDATION_PREFIX + story_id + ':' + record_id


def write_invalidation(db, record: LinkInvalidation) -> None:
    """Inside the caller's transaction."""
    db.execute('INSERT INTO app_settings VALUES(?,?)', (invalidation_key(record.story_id, record.id), record.model_dump_json()))


def _invalidation_ok(key, record, scenes) -> bool:
    scene = scenes.get(record.scene_id)
    return key == invalidation_key(record.story_id, record.id) and scene is not None and scene.story_id == record.story_id


def load_invalidations(db, story_id: str, scenes, order: dict | None = None) -> list[LinkInvalidation]:
    """Records of the story in insertion order; `order` receives {record id: rowid}. A foreign key or scene is damage."""
    records = []
    for rowid, key, payload in db.execute('SELECT rowid,key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',
                                          (INVALIDATION_PREFIX + story_id + ':%',)):
        record = LinkInvalidation.model_validate_json(payload)
        if record.story_id != story_id or not _invalidation_ok(key, record, scenes):
            raise ValueError('Пошкоджений журнал інвалідації зв’язків')
        records.append(record)
        if order is not None:
            order[record.id] = rowid
    return records


def check_invalidations(db, scenes, report) -> None:
    """fsck: key shape, model and scene ownership of every invalidation."""
    for key, payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'link_invalidation:%' ORDER BY rowid"):
        try:
            if not _invalidation_ok(key, LinkInvalidation.model_validate_json(payload), scenes):
                raise ValueError('Invalid record')
        except (ValueError, TypeError):
            report.add('invalid_link_invalidation', key, 'Invalid format or ownership of a link invalidation')
