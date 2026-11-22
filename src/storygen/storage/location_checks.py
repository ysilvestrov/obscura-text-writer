"""Integrity of location cards (MEMORY-LOCATIONS): valid payloads of their own story and scene references to them."""
from .locations import StoryLocation


def check_locations(report, db, scenes):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='story_locations'").fetchone():return
    known=set()
    for id,story_id,payload in db.execute('SELECT id,story_id,payload FROM story_locations'):
        try:card=StoryLocation.model_validate_json(payload)
        except ValueError:
            report.add('invalid_payload',id,'Invalid location card');continue
        if card.id!=id or card.story_id!=story_id:report.add('payload_mismatch',id,'Payload does not match the SQL columns')
        known.add((story_id,id))
    for scene in scenes.values():
        if any((scene.story_id,id) not in known for id in scene.location_ids):
            report.add('location_unknown',scene.id,'Scene refers to a missing location card')
