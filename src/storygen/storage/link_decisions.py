"""VALID-LINKS-S08: the author's decision on a link of a scene, CAS on the link fingerprint."""
from ..domain import RevisionConflict, now
from .context_view import ContextView
from .link_records import LinkVerdict, new_verdict_id, write_verdict
from .links import link_state, scene_validity

# Z3 «keep the previous memory» also records a prose equivalence (plan 2b); until then it is refused.
DECIDABLE = {'brief', 'prose'}


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
        if state.status in {'missing', 'unavailable'} or state.fingerprint != fingerprint:
            raise RevisionConflict('Зв’язок сцени змінився; оновіть сторінку')
        if state.status != 'valid':
            write_verdict(db, LinkVerdict(id=new_verdict_id(), story_id=scene.story_id, scene_id=scene_id, link=link,
                                          inputs=state.inputs, fingerprint=fingerprint, source='author', outcome='valid',
                                          created_at=now()))
            view = ContextView(repo, db, scene.story_id)
            state = link_state(view, scene_id, link)
        return {'link': state.as_dict(), 'validity': scene_validity(view, scene_id)}
