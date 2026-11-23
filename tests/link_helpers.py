"""VALID-LINKS in tests: hand-made fixtures (raw save_version of briefs, prose and memory) stand in for material the
author has confirmed. approve_links writes the author's verdict for every unchecked link of the story, as the panel
would; call it explicitly at the end of a fixture, never autouse, so the rule stays visible in each test file."""
from storygen.domain import now
from storygen.storage.link_records import LinkVerdict, new_verdict_id, write_verdict
from storygen.storage.links import scene_links


def approve_links(repo, story_id, scene_ids=None):
    view = repo.context_view(story_id)
    records = []
    for scene in view.scenes.values():
        if scene.trashed_at or (scene_ids is not None and scene.id not in scene_ids):
            continue
        for link, state in scene_links(view, scene.id).items():
            if state.status in {'unchecked', 'discrepancy'}:
                records.append(LinkVerdict(id=new_verdict_id(), story_id=story_id, scene_id=scene.id, link=link,
                                           inputs=state.inputs, fingerprint=state.fingerprint, source='author',
                                           outcome='valid', created_at=now()))
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for record in records:
            write_verdict(db, record)
    return len(records)
