"""VALID-LINKS-S08: the author's decision on a link of a scene, CAS on the link fingerprint."""
from ..domain import RevisionConflict, now
from .context_view import ContextView
from .link_records import LinkVerdict, ProseEquivalence, new_verdict_id, write_equivalence, write_verdict, PROSE_KINDS
from .links import link_state, scene_links, scene_validity

# Z3 «keep the previous memory» also records a prose equivalence. An unavailable link (carry_failed, no memory) is a
# conflict: only a new memory of the scene clears it.
DECIDABLE = {'brief', 'prose', 'memory'}
CARRY_FAILED = 'Пам’ять сцени не перенесено на нову пам’ять попередньої сцени, і рішення автора її не залишить — створіть нову пам’ять цієї сцени'


class LinkDecisionRefused(ValueError):
    """The link cannot take this decision (422)."""


def decide_link(repo, scene_id: str, link: str, action: str, fingerprint: str) -> dict:
    if link not in DECIDABLE or action != 'approve':
        raise LinkDecisionRefused('Для цього зв’язку немає такого рішення')
    scene = repo.get_scene(scene_id)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        view = ContextView(repo, db, scene.story_id)
        state = link_state(view, scene_id, link)
        if state.reason == 'carry_failed':
            raise RevisionConflict(CARRY_FAILED)
        if state.reason == 'carry_pending':
            from ..memory.carry import carry_refusal
            raise RevisionConflict(carry_refusal(view, scene_id))
        if state.status in {'missing', 'unavailable'} or state.fingerprint != fingerprint:
            raise RevisionConflict('Зв’язок сцени змінився; оновіть сторінку')
        if state.status != 'valid':
            verdict = LinkVerdict(id=new_verdict_id(), story_id=scene.story_id, scene_id=scene_id, link=link,
                                  inputs=state.inputs, fingerprint=fingerprint, source='author', outcome='valid',
                                  created_at=now())
            write_verdict(db, verdict)
            if link == 'memory':
                _record_equivalence(db, view, scene_id, verdict)
            view = ContextView(repo, db, scene.story_id)
            state = link_state(view, scene_id, link)
        return {'link': state.as_dict(), 'validity': scene_validity(view, scene_id)}


def _record_equivalence(db, view, scene_id, verdict) -> None:
    """The prose the kept memory was made from (the last source of its journal) is equivalent to the current prose."""
    from ..memory.journal import load_memory
    heads = view.scenes[scene_id].heads
    sources = load_memory(view.read_text(heads['memory'])).source_prose_ids
    old = sources[-1] if sources else None
    ref = view.versions.get(old) if old else None
    if ref is not None and ref.scene_id == scene_id and ref.kind in PROSE_KINDS and old != heads['prose']:
        write_equivalence(db, ProseEquivalence(id=new_verdict_id(), story_id=verdict.story_id, scene_id=scene_id,
                                               old_prose_id=old, new_prose_id=heads['prose'], verdict_id=verdict.id,
                                               created_at=verdict.created_at))


class InvalidationTargetMissing(KeyError):
    """A scene of the request is unknown, trashed or belongs to another story (404)."""


def invalidate_links(repo, story_id: str, scene_ids: list[str], reason: dict) -> list[str]:
    """VALID-LINKS rule (г): the author's «Так» after a card or location change. One transaction; for every scene one
    LinkInvalidation of Z1 and Z2 with their current fingerprints (a missing or unavailable link is skipped, a scene with
    neither writes nothing). Returns the scenes that got a record."""
    from .link_records import InvalidationReason, LinkInvalidation, write_invalidation, CARD_LINKS
    cause = InvalidationReason.model_validate(reason)
    written = []
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        view = ContextView(repo, db, story_id)  # an unknown or trashed story raises KeyError
        for scene_id in scene_ids:
            scene = view.scenes.get(scene_id)
            if scene is None or scene.trashed_at:
                raise InvalidationTargetMissing(scene_id)
        stamp = now()
        for scene_id in dict.fromkeys(scene_ids):
            states = scene_links(view, scene_id)
            links = [link for link in CARD_LINKS if states[link].status not in {'missing', 'unavailable'}]
            if not links:
                continue
            write_invalidation(db, LinkInvalidation(id=new_verdict_id(), story_id=story_id, scene_id=scene_id, links=links,
                                                    fingerprints={link: states[link].fingerprint for link in links},
                                                    reason=cause, created_at=stamp))
            written.append(scene_id)
    return written


def write_auditor_verdict(repo, story_id: str, scene_id: str, link: str, *, fingerprint: str | None, marker: int | None,
                          outcome: str, confidence: int | None = None, discrepancies=(), reason: str | None = None,
                          attempt_id: str | None = None, run_id: str | None = None) -> tuple[str, str | None]:
    """VALID-LINKS: the auditor's verdict in one transaction with CAS. ('written', id); ('stale', None) when the link
    fingerprint differs from `fingerprint` or, with a `marker`, an invalidation of this scene has a rowid above it;
    ('structural', None) when link_state itself reports the link unavailable (no previous memory, carry, no memory):
    such a state clears with its cause, while a record would outlive it under the same fingerprint."""
    from .link_records import load_latest_invalidation_rowid
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        view = ContextView(repo, db, story_id)
        state = link_state(view, scene_id, link)
        if state.status == 'unavailable' and state.source is None:
            return 'structural', None
        if fingerprint is None or state.status == 'missing' or state.fingerprint != fingerprint:
            return 'stale', None
        if marker is not None and load_latest_invalidation_rowid(db, story_id) > marker and any(
                record.scene_id == scene_id and view.link_order[record.id] > marker for record in view.link_invalidations):
            return 'stale', None
        verdict = LinkVerdict(id=new_verdict_id(), story_id=story_id, scene_id=scene_id, link=link, inputs=state.inputs,
                              fingerprint=fingerprint, source='auditor', outcome=outcome, confidence=confidence,
                              discrepancies=list(discrepancies), reason=reason, attempt_id=attempt_id, run_id=run_id,
                              created_at=now())
        write_verdict(db, verdict)
        if link == 'memory' and outcome == 'valid':
            _record_equivalence(db, view, scene_id, verdict)  # Z3 kept after a prose change (design §4)
    return 'written', verdict.id
