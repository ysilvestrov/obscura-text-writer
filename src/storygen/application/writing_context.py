"""MCP-BRIDGE read model: what an external chat client needs to write a scene draft. No prompts, keys or model calls."""
import hashlib
import json

from ..characters.context import character_material
from ..generation.context import memory_projection
from ..rating.levels import effective_rating


def _content(view,story,scene) -> dict:
    scenes=view.list_scenes(story.id)
    characters,character_warnings,_=character_material(view,story,scene)
    *_,projection=memory_projection(view,story,scene,scenes,story.language)
    plan=view.read_text(scene.heads['plan']) if scene.heads.get('plan') else scene.beats
    brief=view.read_text(scene.heads['brief']) if scene.heads.get('brief') else None
    rating=effective_rating(story,scene)
    return {'story_id':story.id,'scene_id':scene.id,'title':scene.title,'position':scene.position,'scene_count':len(scenes),
            'plan':plan,'brief':brief,'characters':characters,'character_warnings':list(character_warnings),'memory':projection.text,
            'rating':rating.model_dump() if rating else None,'language':scene.prose_language or story.language,
            'story_language':story.language,'target_words':scene.target_words}


def _fingerprint(repo,scene,content: dict) -> str:
    # Lazy: generation.dependencies imports this module for the write-side check.
    from ..generation.dependencies import _manual_snapshot
    payload={'snapshot':_manual_snapshot(repo,scene,'draft').model_dump(mode='json'),'content':content}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def _read(repo,scene_id: str):
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    story=view.get_story(scene.story_id);scene=view.get_scene(scene_id)
    content=_content(view,story,scene)
    return scene,content,_fingerprint(repo,scene,content)


def context_fingerprint(repo,scene_id: str) -> str:
    """SHA-256 of everything writing-context returns (except the revision, checked on its own) plus the draft snapshot:
    a story-level change that does not bump the scene revision (cards, rating, story language, earlier memory) changes it."""
    return _read(repo,scene_id)[2]


def writing_context(repo,scene_id: str) -> dict:
    scene,content,fingerprint=_read(repo,scene_id)
    return {**content,'revision':scene.revision,'context_fingerprint':fingerprint}


def story_list(repo) -> list[dict]:
    result=[]
    for story in repo.list_stories():
        rating=story.content_rating
        result.append({'id':story.id,'title':story.title,'language':story.language,'rating':rating.model_dump() if rating else None,
                       'scene_count':len(repo.context_view(story.id).list_scenes(story.id))})
    return result
