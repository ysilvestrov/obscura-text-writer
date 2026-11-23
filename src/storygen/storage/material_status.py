"""Per-scene state of brief, prose and memory heads, from freshness alone (R-44 PR 1 replaces R-28 scene_status)."""


def material_status(view):
    """{scene_id: {brief, prose: pending|current|missing, memory: needs_update|current|missing}}.

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
        rows[scene.id]=values
    return rows
