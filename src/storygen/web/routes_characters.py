from fastapi import APIRouter,Request
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
