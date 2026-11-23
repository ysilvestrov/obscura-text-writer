"""Per-scene state of brief, prose and memory heads, from freshness alone (R-44 PR 1 replaces R-28 scene_status)."""


from .links import scene_links, scene_validity


def material_status(view):
    """{scene_id: {brief, prose: pending|current|missing, memory: needs_update|current|missing, links, validity}}.

    links: {brief|prose|memory: {status, source, reason, fingerprint}} and validity of the scene (VALID-LINKS).

    Read-only: shared view models (peek_*) and the recomputed stale flag; get_version would deep-copy each head."""
    def stale(id):
        view.peek_version(id)
        return view.is_stale(id)
    rows={}
    for scene in view.peek_scenes(view.story.id):
        values={}
        for material in ('brief','prose'):
            id=scene.heads.get(material)
            waiting=id and (stale(id) or material=='prose' and view.effective_scene(scene.id).needs_review)
            values[material]='missing' if not id else 'pending' if waiting else 'current'
        id=scene.heads.get('memory')
        values['memory']='missing' if not id else 'needs_update' if stale(id) else 'current'
        states=scene_links(view,scene.id)
        values['links']={link:state.as_dict() for link,state in states.items()}
        values['validity']=scene_validity(view,scene.id)
        rows[scene.id]=values
    return rows
