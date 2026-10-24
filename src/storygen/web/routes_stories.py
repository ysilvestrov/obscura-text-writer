from fastapi import APIRouter, Request

from ..authoring.imports import SourceFile, import_sources
from ..authoring.service import reorder_scenes, update_scene, update_scene_plan, rename_story
from ..domain import DomainModel, SceneCreate, StoryCreate

router=APIRouter()


class StoryTitlePatch(DomainModel):
    title: str
    expected_revision: int


class ScenePatch(DomainModel):
    story_id: str
    expected_revision: int
    beats: str | None=None
    title: str | None=None
    target_words: int | None=None
    character_ids: list[str] | None=None


@router.get("/")
def library(request: Request):
    return request.app.state.templates.TemplateResponse(request=request,name="library.html",context={"stories":request.app.state.repo.list_stories()})


@router.get("/stories/{id}")
def story_page(id: str,request: Request):
    return request.app.state.templates.TemplateResponse(request=request,name="story.html",context={"story":request.app.state.repo.get_story(id)})


@router.post("/api/stories")
def create_story(data: StoryCreate,request: Request):
    return request.app.state.repo.create_story(data)


@router.get("/api/stories/{id}")
def story_view(id: str,request: Request):
    view=request.app.state.repo.context_view(id)
    story=view.get_story(id)
    from ..characters.models import load_characters
    names={card.id:card.name for card in load_characters(view.read_text(story.characters_version_id))} if story.characters_version_id else {}
    return {"story":story,"scenes":[view.effective_scene(scene.id) for scene in view.list_scenes(id)],"sources":[view.get_version(v.id) for v in view.versions.values() if v.kind in {"source_plan","source_characters"}],"character_names":names}


@router.patch('/api/stories/{id}')
def story_title(id: str,body: StoryTitlePatch,request: Request):
    return rename_story(request.app.state.repo,id,body.title,body.expected_revision)


@router.post("/api/stories/{id}/sources")
async def sources(id: str,request: Request):
    form=await request.form(max_part_size=2*1024*1024+1024)
    uploads=[]
    for name,item in form.multi_items():
        if hasattr(item,"read"):
            uploads.append(SourceFile(name=item.filename or "source.txt",raw=await item.read(2*1024*1024+1),kind="source_characters" if name=="characters" else "source_plan"))
            await item.close()
    if not uploads:
        raise ValueError("Виберіть план або персонажів")
    return import_sources(request.app.state.repo,id,uploads)


@router.post("/api/stories/{id}/scenes")
def add_scene(id: str,data: SceneCreate,request: Request):
    return request.app.state.repo.create_scene(id,data)


@router.patch("/api/scenes/{id}")
def patch_scene(id: str,data: ScenePatch,request: Request):
    repo=request.app.state.repo
    if repo.get_scene(id).story_id!=data.story_id:
        raise ValueError("Сцена належить іншому твору")
    scene=repo.get_scene(id)
    revision=data.expected_revision
    if data.beats is not None:
        scene=update_scene_plan(repo,id,data.beats,revision)
        revision=scene.revision
    changes={key:value for key,value in data.model_dump().items() if key in {"title","target_words","character_ids"} and value is not None}
    return update_scene(repo,id,changes,revision) if changes else scene


class SceneOrder(DomainModel):
    scene_ids: list[str]
    expected_revision: int


@router.put("/api/stories/{id}/scene-order")
def order(id: str,data: SceneOrder,request: Request):
    return reorder_scenes(request.app.state.repo,id,data.scene_ids,data.expected_revision)


class TrashChange(DomainModel):
    expected_revision: int


class SceneTrashChange(TrashChange):
    story_id: str


@router.get('/api/trash')
def trash_view(request: Request):
    return {'stories':[s for s in request.app.state.repo.list_stories(include_trashed=True) if s.trashed_at]}


@router.get('/api/stories/{id}/trash')
def scene_trash_view(id: str,request: Request):
    return {'scenes':[s for s in request.app.state.repo.list_scenes(id,include_trashed=True) if s.trashed_at]}


@router.post('/api/stories/{id}/trash')
def story_trash(id: str,data: TrashChange,request: Request):
    from ..authoring.trash import trash_story
    return trash_story(request.app.state.repo,id,data.expected_revision)


@router.post('/api/stories/{id}/restore')
def story_restore(id: str,data: TrashChange,request: Request):
    from ..authoring.trash import restore_story
    return restore_story(request.app.state.repo,id,data.expected_revision)


@router.post('/api/scenes/{id}/trash')
def scene_trash(id: str,data: SceneTrashChange,request: Request):
    from ..authoring.trash import trash_scene
    return trash_scene(request.app.state.repo,data.story_id,id,data.expected_revision)


@router.post('/api/scenes/{id}/restore')
def scene_restore(id: str,data: SceneTrashChange,request: Request):
    from ..authoring.trash import restore_scene
    return restore_scene(request.app.state.repo,data.story_id,id,data.expected_revision)
