from typing import Literal

from fastapi import APIRouter,Request

router=APIRouter()


@router.get('/api/scenes/{scene_id}/comments')
def comments(scene_id: str,request: Request,material: Literal['draft']='draft'):
    return request.app.state.repo.get_comment_state(scene_id)
