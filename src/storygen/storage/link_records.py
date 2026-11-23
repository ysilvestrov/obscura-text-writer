"""VALID-LINKS: append-only verdicts on the three links of a scene, kept in app_settings without a migration.

A verdict holds for the link's fingerprint at the time it was written; a changed component changes the fingerprint and
the verdict stops applying. The last record for (scene, link, fingerprint) wins."""
from typing import Literal
from pydantic import Field
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


def load_verdicts(db, story_id: str, scenes) -> dict[tuple[str, str, str], LinkVerdict]:
    """{(scene_id, link, fingerprint): last verdict}; a record under a foreign key or for a foreign scene is damage."""
    verdicts = {}
    for key, payload in db.execute('SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',
                                   (PREFIX + story_id + ':%',)):
        record = LinkVerdict.model_validate_json(payload)
        scene = scenes.get(record.scene_id)
        if record.story_id != story_id or key != verdict_key(story_id, record.id) or scene is None or scene.story_id != story_id:
            raise ValueError('Пошкоджений журнал висновків про зв’язки')
        verdicts[(record.scene_id, record.link, record.fingerprint)] = record
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
