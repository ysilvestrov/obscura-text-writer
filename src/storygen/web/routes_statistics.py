from typing import Literal
from fastapi import APIRouter,Request
from ..application.statistics import scene_statistics

router=APIRouter()


@router.get('/api/scenes/{scene_id}/statistics')
def statistics(scene_id: str,request: Request,stage: Literal['brief','draft','edit','memory']='draft'):
    return scene_statistics(request.app.state.repo,scene_id,stage)
