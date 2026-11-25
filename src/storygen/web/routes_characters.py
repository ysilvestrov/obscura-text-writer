from fastapi import APIRouter,Request
from pydantic import Field
from ..domain import DomainModel
from ..characters.service import read_character_material,save_character_material,preview_character_material

router=APIRouter()


class CharacterChange(DomainModel):
    expected_revision: int
    cards: list[dict]


class CharacterPreview(DomainModel):
    scene_id: str
    cards: list[dict]


@router.get('/api/stories/{story_id}/characters')
def read(story_id: str,request: Request,scene_id: str | None=None):
    return read_character_material(request.app.state.repo,story_id,scene_id)


@router.put('/api/stories/{story_id}/characters')
def save(story_id: str,body: CharacterChange,request: Request):
    return save_character_material(request.app.state.repo,story_id,body.cards,body.expected_revision)


@router.post('/api/stories/{story_id}/characters/preview')
def preview(story_id: str,body: CharacterPreview,request: Request):
    return preview_character_material(request.app.state.repo,story_id,body.cards,body.scene_id)


from ..characters.brief_link import BriefLinkBody


@router.get('/api/scenes/{scene_id}/brief-link')
def brief_link_view(scene_id: str,request: Request):
    from ..characters.brief_link import brief_link_state
    repo=request.app.state.repo
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    return brief_link_state(view,view.get_story(scene.story_id),view.get_scene(scene_id))


@router.post('/api/scenes/{scene_id}/brief-link')
def brief_link_confirm(scene_id: str,body: BriefLinkBody,request: Request):
    from ..characters.brief_link import confirm_brief_link
    return confirm_brief_link(request.app.state.repo,scene_id,body)


class ExtractPreview(DomainModel):
    group_words: int = Field(default=5000,ge=1000,le=20000,strict=True)


@router.post('/api/stories/{story_id}/character-extract/preview')
def character_extract_preview(story_id: str,body: ExtractPreview,request: Request):
    # CHARACTER-EXTRACT (R-51): read-only; the plan of the run — groups, calls bound, cost, fingerprint.
    from ..characters.extract_plan import extract_plan
    return extract_plan(request.app.state.repo,story_id,body.group_words)


from ..characters.extract_accept import AcceptRequest


@router.get('/api/stories/{story_id}/character-proposal')
def character_proposal(story_id: str,request: Request):
    # CHARACTER-EXTRACT (R-51): the proposal of the latest finished run while it can be accepted, with its run_id.
    from fastapi import HTTPException
    from ..characters.extract_accept import NO_PROPOSAL,current_proposal
    repo=request.app.state.repo
    repo.get_story(story_id)
    proposal=current_proposal(repo,story_id)
    if proposal is None:
        raise HTTPException(404,NO_PROPOSAL)
    return proposal


@router.post('/api/stories/{story_id}/character-proposal/accept')
def character_proposal_accept(story_id: str,body: AcceptRequest,request: Request):
    # One transaction: cards, casts and the accepted mark; `dry_run` answers the same and writes nothing.
    from ..characters.extract_accept import accept_proposal
    return accept_proposal(request.app.state.repo,story_id,body)
