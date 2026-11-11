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
    # BUILD-EDITION-001: these are writing instructions for an external model, so the edition limit applies —
    # to the rating of this very snapshot, not to a separate read that a concurrent change could outdate.
    from ..domain import ContentRating
    from ..rating.guard import enforce_rating_limit
    enforce_rating_limit(ContentRating(**content['rating']) if content['rating'] else None)
    return {**content,'revision':scene.revision,'context_fingerprint':fingerprint}


def story_list(repo) -> list[dict]:
    result=[]
    for story in repo.list_stories():
        rating=story.content_rating
        result.append({'id':story.id,'title':story.title,'language':story.language,'rating':rating.model_dump() if rating else None,
                       'scene_count':len(repo.context_view(story.id).list_scenes(story.id))})
    return result


MATERIALS=('plan','brief','draft','prose','memory')
MEMORY_FIELDS=('claim_id','category','text','source_scene','source_title','quote','supporting_quotes','forward','closed')


def scene_text(repo,scene_id: str,material: str,offset: int=0,max_chars: int=20000) -> dict:
    """MCP-BRIDGE (#108): one scene material as it is now, with the head version and a hash of the whole text,
    sliced by characters. The hash, not the version, tells parts apart: memory forwarding changes the table without a new version."""
    if material not in MATERIALS:raise ValueError(f'Невідомий матеріал сцени: {material}')
    from ..memory.forwarding import memory_view_from_view
    from ..rating.guard import enforce_rating_limit
    owner=repo.get_scene(scene_id)
    view=repo.context_view(owner.story_id)
    story=view.get_story(owner.story_id);scene=view.get_scene(scene_id)
    # BUILD-EDITION-001: the text goes to an external model, as the writing context does.
    enforce_rating_limit(effective_rating(story,scene))
    head=scene.heads.get(material)
    ref=view.get_version(head) if head else None
    if material=='memory':
        rows=memory_view_from_view(view,scene_id)['rows'] if head else []
        text=json.dumps([{key:row[key] for key in MEMORY_FIELDS} for row in rows],ensure_ascii=False,sort_keys=True) if rows else ''
    elif material=='plan' and not head:
        text=scene.beats or ''
    else:
        text=view.read_text(head) if head else ''
    total=len(text)
    if offset<0 or offset>total:raise ValueError(f'offset має бути від 0 до {total}')
    end=min(offset+max_chars,total)
    return {'scene_id':scene.id,'story_id':story.id,'material':material,'revision':scene.revision,'version_id':head,
            'kind':ref.kind if ref else None,'content_format':ref.content_format if ref else None,'stale':bool(ref and ref.stale),
            'external_origin':ref.external_origin.model_dump() if ref and ref.external_origin else None,
            'text':text[offset:end],'offset':offset,'total_chars':total,'next_offset':end if end<total else None,
            'content_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest()}
