"""MCP-BRIDGE read model: what an external chat client needs to write a scene draft. No prompts, keys or model calls."""
from ..characters.context import character_material
from ..generation.context import memory_projection
from ..generation.dependencies import writing_fingerprint
from ..rating.levels import effective_rating


def writing_context(repo,scene_id: str) -> dict:
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    story=view.get_story(scene.story_id);scene=view.get_scene(scene_id)
    scenes=view.list_scenes(story.id)
    characters,character_warnings,_=character_material(view,story,scene)
    *_,projection=memory_projection(view,story,scene,scenes,story.language)
    plan=view.read_text(scene.heads['plan']) if scene.heads.get('plan') else scene.beats
    brief=view.read_text(scene.heads['brief']) if scene.heads.get('brief') else None
    rating=effective_rating(story,scene)
    return {'story_id':story.id,'scene_id':scene.id,'title':scene.title,'position':scene.position,'scene_count':len(scenes),
            'plan':plan,'brief':brief,'characters':characters,'character_warnings':list(character_warnings),'memory':projection.text,
            'rating':rating.model_dump() if rating else None,'language':scene.prose_language or story.language,
            'target_words':scene.target_words,'revision':scene.revision,'context_fingerprint':writing_fingerprint(repo,repo.get_scene(scene_id))}


def story_list(repo) -> list[dict]:
    result=[]
    for story in repo.list_stories():
        rating=story.content_rating
        result.append({'id':story.id,'title':story.title,'language':story.language,'rating':rating.model_dump() if rating else None,
                       'scene_count':len(repo.context_view(story.id).list_scenes(story.id))})
    return result
