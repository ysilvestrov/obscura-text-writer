"""#44: does a scene's accepted prose need the author's brief confirmation, and recording it."""
from pydantic import Field
from ..domain import DomainModel
from ..generation.models import WritersBrief
from .acquaintance import lineage_source,protagonist
from .models import load_characters


class BriefLinkBody(DomainModel):
    prose_version_id: str = Field(min_length=1)
    brief_version_id: str = Field(min_length=1)
    introduced: list[str] = Field(default_factory=list,max_length=1000)
    expected_revision: int


def _brief_data(view,ref_id):
    try:return WritersBrief.model_validate_json(view.read_text(ref_id))
    except (ValueError,KeyError,OSError):return None


def _context(view,story):
    cards=load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
    scenes=[item for item in view.list_scenes(story.id) if not item.trashed_at]
    hero,_=protagonist(cards,scenes) if cards else (None,[])
    return cards,scenes,hero


def _scene_state(view,scene,hero):
    """(needed, source, lineage_introduced): the same lineage walk the acquaintance count uses."""
    found=lineage_source(view,scene)
    if found is None:source,introduced='fallback',None
    elif found[0]=='link':source,introduced='link',list(found[1].brief_link.introduced)
    else:
        data=_brief_data(view,found[1].id)
        source,introduced='lineage',(data.introduced if data else None)
    others=[cid for cid in scene.character_ids if cid!=hero]
    eligible=bool(scene.heads.get('prose') and scene.heads.get('brief') and hero and hero in scene.character_ids and others)
    needed=eligible and source!='link' and introduced is None
    return needed,source,introduced


def brief_link_state(view,story,scene):
    cards,scenes,hero=_context(view,story)
    needed,source,lineage_introduced=_scene_state(view,scene,hero)
    names={card.id:card.name for card in cards}
    others=[cid for cid in scene.character_ids if cid!=hero]
    prose_id=scene.heads.get('prose')
    link=view.get_version(prose_id).brief_link if prose_id else None
    if source=='link':
        found=lineage_source(view,scene);link=found[1].brief_link
    brief_id=scene.heads.get('brief')
    brief=None;head_introduced=None
    if brief_id:
        ref=view.get_version(brief_id);data=_brief_data(view,brief_id)
        head_introduced=data.introduced if data else None
        objective=(data.objective.strip().split('\n\n')[0] if data else '')
        brief={'version_id':brief_id,'objective':objective,'stale':view.is_stale(brief_id)}
    if link is not None:checked=set(link.introduced)
    elif head_introduced is not None:checked=set(head_introduced)
    elif lineage_introduced is not None:checked=set(lineage_introduced)
    else:checked=set()
    ordered=sorted(scenes,key=lambda item:item.position)
    pending=[item for item in ordered if item.id!=scene.id and _scene_state(view,item,hero)[0]]
    after=[item for item in pending if item.position>scene.position]
    next_scene=(after or pending or [None])[0]
    return {'needed':needed,'source':source,'hero_id':hero,'hero_name':names.get(hero) if hero else None,
        'prose_version_id':prose_id,'brief':brief,'link':link.model_dump() if link else None,
        'cast':[{'id':cid,'name':names.get(cid,cid),'checked':cid in checked} for cid in others],
        'next_scene_id':next_scene.id if next_scene else None,'revision':scene.revision}


def confirm_brief_link(repo,scene_id,body: BriefLinkBody):
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    story=view.get_story(scene.story_id)
    _,_,hero=_context(view,story)
    allowed={cid for cid in view.get_scene(scene_id).character_ids if cid!=hero}
    ref=repo.confirm_brief_link(scene_id,body.prose_version_id,body.brief_version_id,body.introduced,body.expected_revision,allowed=allowed)
    return {'version':ref,'scene':repo.get_scene(scene_id)}
