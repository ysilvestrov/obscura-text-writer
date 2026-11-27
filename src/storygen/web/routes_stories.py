from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import Field
from fastapi.responses import JSONResponse

from ..authoring.imports import SourceFile, import_sources, ImportBatchConflict, ImportBatchFailure, ImportTooLarge
from ..authoring.service import reorder_scenes, update_scene, update_scene_plan, rename_story
from ..domain import DomainModel, RevisionConflict, Scene, SceneCreate, SceneNarrator, StoryCreate

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
    # 'story' resets the override so the scene follows the story language again; None leaves it unchanged.
    prose_language: Literal['uk','en','story'] | None=None
    # STORY-TIME: the flashback flag; None leaves it unchanged.
    flashback: bool | None=None
    # SCENE-NARRATOR: null resets to the story style; a missing field leaves it unchanged.
    narrator: SceneNarrator | None=None
    # MCP-BRIDGE-S19: the plan head the external client read; null means it read a scene without a plan version.
    expected_plan_version_id: str | None=Field(default=None,max_length=64)


class StoryLanguageChange(DomainModel):
    language: Literal['uk','en']
    expected_revision: int


class StoryWritingModeChange(DomainModel):
    writing_mode: Literal['chat','obscura','author']
    expected_revision: int


@router.put("/api/stories/{id}/writing-mode")
def change_writing_mode(id: str,data: StoryWritingModeChange,request: Request):
    """WRITING-MODE-S02/S04: the author's choice; the bridge may not change it."""
    from .bridge_marker import MODE_OWNER_ONLY, BridgeForbidden, from_bridge
    if from_bridge(request):
        raise BridgeForbidden(MODE_OWNER_ONLY)
    return request.app.state.repo.update_writing_mode(id,data.writing_mode,data.expected_revision)


@router.put("/api/stories/{id}/language")
def change_story_language(id: str,data: StoryLanguageChange,request: Request):
    return request.app.state.repo.update_story_language(id,data.language,data.expected_revision)


@router.get("/")
def library(request: Request):
    return request.app.state.templates.TemplateResponse(request=request,name="library.html",context={"entries":_library_entries(request.app.state.repo)})


def _library_entries(repo):
    # SERIES-LIBRARY: series books gathered into a group that stands where its newest book stands.
    from ..book.library import library_entries
    from ..storage import series as series_store
    return library_entries(repo.list_stories(),series_store.list_series(repo))


@router.get("/stories/{id}")
def story_page(id: str,request: Request):
    return request.app.state.templates.TemplateResponse(request=request,name="story.html",context={"story":request.app.state.repo.get_story(id)})


@router.get("/stories/{id}/revision")
def revision_page(id: str,request: Request):
    """The book check page of R-28 is removed (R-44 PR 1); old links and bookmarks open the story."""
    request.app.state.repo.get_story(id)
    return RedirectResponse(f"/stories/{id}",status_code=303)


@router.get("/stories/{id}/characters")
def characters_page(id: str,request: Request):
    return request.app.state.templates.TemplateResponse(request=request,name="characters.html",context={"story":request.app.state.repo.get_story(id)})


@router.get("/stories/{id}/locations")
def locations_page(id: str,request: Request):
    """MEMORY-LOCATIONS-S12: the story's locations on their own page, like the characters."""
    return request.app.state.templates.TemplateResponse(request=request,name="locations.html",context={"story":request.app.state.repo.get_story(id)})


@router.get("/api/stories")
def stories_list(request: Request):
    """MCP-BRIDGE: active stories for an external client; the HTML library stays at `/`."""
    from ..application.writing_context import story_list
    return story_list(request.app.state.repo)


@router.post("/api/stories")
def create_story(data: StoryCreate,request: Request):
    return request.app.state.repo.create_story(data)


def prose_origin(view,scene):
    """R-48 MANUSCRIPT-IMPORT (spec §4.4): where the scene's prose head came from, so the status row names the manuscript
    file; None for author or model prose, no prose, or a head on a missing version (the view stays readable)."""
    prose=scene.heads.get("prose")
    ref=view.versions.get(prose) if prose else None
    origin=ref.manuscript_import if ref is not None else None
    return {"kind":"manuscript_import","file_name":origin.file_name} if origin else None


@router.get("/api/stories/{id}")
def story_view(id: str,request: Request):
    view=request.app.state.repo.context_view(id)
    story=view.get_story(id)
    from ..characters.models import load_characters
    cards=load_characters(view.read_text(story.characters_version_id)) if story.characters_version_id else []
    names={card.id:card.name for card in cards}
    from ..storage.material_status import material_status
    from ..rating.levels import effective_rating
    listed=view.list_scenes(id)
    ratings={scene.id:{"effective":effective_rating(story,scene),"source":"scene" if scene.content_rating else "story" if story.content_rating else None} for scene in listed}
    from ..book.structure import effective_structure
    # BOOK-STRUCTURE: the effective structure (implicit for a flat book) and each scene's arc.
    structure=effective_structure(story,listed)
    from ..memory.story_time import is_flashback
    from ..book.story_time import arc_start
    from ..memory.story_time import Moment
    unknown_moment=Moment('unknown',None,None,False)
    # STORY-TIME: arcs whose start is unknown, shown only when the book has a flashback (the start decides what it sees).
    unknown=[arc.id for part in structure.parts for arc in part.arcs if (arc_start(story,listed,arc.id) or unknown_moment).kind=='unknown'] if (
        structure.kind=='structured' and any(is_flashback(scene) for scene in listed)) else []
    book={"kind":structure.kind,"explicit":structure.explicit,"parts":[part.model_dump() for part in structure.parts],"arc_start_unknown":unknown}
    # arc_id stays the first arc for old clients; arc_ids lists every arc of a meeting scene (MEMORY-MERGE harness).
    from ..storage.memory_merges import merge_markers
    from ..memory.story_time import flashback_marked
    marks=merge_markers(view,story,listed) if story.book_structure is not None else {}
    from ..narration import narrator_card
    scenes=[{**view.effective_scene(scene.id).model_dump(),"prose_origin":prose_origin(view,scene),"arc_id":structure.arc_of.get(scene.id),"arc_ids":list(structure.arcs_of.get(scene.id,())),"memory_merge":marks.get(scene.id),
        "flashback_marked":flashback_marked(scene.beats),**narrator_card(scene,cards)} for scene in listed]
    from .routes_series import series_block
    # SERIES: the block is present only for a book in a series.
    series=series_block(request.app.state.repo,story)
    extra={"series":series} if series else {}
    # LONG-PROSE-TRIAL-S07: the book modules ask the book, not the build (no database read with long prose).
    from ..book.guard import long_prose_for
    return {**extra,"long_prose":long_prose_for(request.app.state.repo,story),"material_status":material_status(view),"language_locked":request.app.state.repo.story_language_locked(id),"story":story,"book_structure":book,"scenes":scenes,"scene_ratings":ratings,"sources":[view.get_version(v.id) for v in view.versions.values() if v.kind in {"source_plan","source_characters"}],"character_names":names,"source_files":view.source_files,"active_sources":view.sources}


@router.get("/api/stories/{id}/scene-revisions")
def scene_revisions(id: str,request: Request):
    # R-49: the mode rides along, so an open workspace notices a mode switch made in another window; the story revision
    # (MEMORY-LOCATIONS-S12) lets it notice any story-level change made elsewhere, such as on the locations page.
    story=request.app.state.repo.get_story(id)
    return {"scenes":request.app.state.repo.scene_revisions(id),"writing_mode":story.writing_mode,"story_revision":story.revision}


@router.patch('/api/stories/{id}')
def story_title(id: str,body: StoryTitlePatch,request: Request):
    return rename_story(request.app.state.repo,id,body.title,body.expected_revision)


class PlanPreambleChange(DomainModel):
    text: str=Field(max_length=200000)
    expected_plan_version_id: str=Field(max_length=64)


@router.get('/api/stories/{id}/plan-preamble')
def plan_preamble(id: str,request: Request):
    from ..storage.plan_preamble import read_plan_preamble
    return read_plan_preamble(request.app.state.repo,id)


@router.put('/api/stories/{id}/plan-preamble')
def change_plan_preamble(id: str,body: PlanPreambleChange,request: Request):
    """PLAN-PREAMBLE: a new plan version with the same scenes; scenes written with the old preamble need review."""
    from ..storage.plan_preamble import replace_plan_preamble
    from ..storage.material_status import material_status
    repo=request.app.state.repo
    result=replace_plan_preamble(repo,id,body.expected_plan_version_id,body.text)
    return {**result,'material_status':material_status(repo.context_view(id))}


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
    try:return import_sources(request.app.state.repo,id,uploads)
    except ImportBatchConflict as error:return JSONResponse(status_code=409,content=error.result.model_dump())
    except ImportBatchFailure as error:return JSONResponse(status_code=400,content=error.result.model_dump())
    except ImportTooLarge as error:return JSONResponse(status_code=413,content={'detail':str(error)})


@router.post("/api/stories/{id}/scenes")
def add_scene(id: str,data: SceneCreate,request: Request):
    return request.app.state.repo.create_scene(id,data,plan_template=True)


@router.patch("/api/scenes/{id}")
def patch_scene(id: str,data: ScenePatch,request: Request):
    repo=request.app.state.repo
    if repo.get_scene(id).story_id!=data.story_id:
        raise ValueError("Сцена належить іншому твору")
    if 'expected_plan_version_id' in data.model_fields_set and data.beats is None:
        raise ValueError('Ідентифікатор прочитаного плану передається лише разом із планом')
    scene=repo.get_scene(id)
    revision=data.expected_revision
    changes={key:value for key,value in data.model_dump().items() if key in {"title","target_words","character_ids","flashback"} and value is not None}
    if data.prose_language is not None:
        changes['prose_language']=None if data.prose_language=='story' else data.prose_language
    if 'narrator' in data.model_fields_set:
        changes['narrator']=data.narrator
    # The whole patch is validated before the first change, so a bad field leaves neither plan nor properties written.
    Scene.model_validate({**scene.model_dump(),**changes})
    if data.beats is not None:
        read={'expected_plan_version_id':data.expected_plan_version_id} if 'expected_plan_version_id' in data.model_fields_set else {}
        scene=update_scene_plan(repo,id,data.beats,revision,**read)
        revision=scene.revision
        if changes:
            try:return update_scene(repo,id,changes,revision)
            except RevisionConflict as error:
                return JSONResponse(status_code=409,content={'detail':f'{error} План записано, властивості сцени — ні: перечитайте сцену.',
                                                             'detail_original':str(error),'plan_applied':True,'revision':scene.revision})
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
