"""WRITING-MODE: requests from the MCP bridge carry a header; the story mode decides what the chat may write."""
import re

from ..domain import RevisionConflict

# Launches and run controls only the author takes: whole-scene and story runs, preparation, evaluation, impact and book review,
# copyedit classification, memory rebuild, pause/resume and the cancel-before-enqueue path.
_AUTHOR_ONLY=re.compile(r'^/api/(stories/[^/]+/(prepare|evaluate|impact|review)(/.*)?|scenes/[^/]+/(rebuild-memory|copyedits/[^/]+/classify)'
                        r'|runs/(cancel-request|[^/]+/(pause|resume|continue-after-acceptance)))$')

BRIDGE_HEADER='X-Obscura-Client'
OBSCURA_WRITES='Твір у режимі «пише Obscura»: запустіть етап через start_run'
CHAT_WRITES='Твір у режимі «пише чат»: напишіть текст самі (get_stage_task, save_draft)'
RUN_OWNER_ONLY='Цю дію із запуском виконує лише автор в Obscura'
BRIDGE_RUN_MODES=frozenset({'stage','publication_suggest','audit','rebuild_memory','character_extract'})
MEMORY_PLAN_REQUIRED='Побудову пам’яті з чату запускають із відбитком плану, який бачив автор: спершу покажіть перегляд'
EXTRACT_PLAN_REQUIRED='Пошук персонажів з чату запускають із відбитком плану, який бачив автор: спершу покажіть перегляд'
MODE_OWNER_ONLY='Режим твору змінює лише автор в Obscura'


class BridgeForbidden(Exception):
    """An action the bridge may never take; the app answers 403 with a localized detail."""


def from_bridge(request) -> bool:
    return request.headers.get(BRIDGE_HEADER)=='mcp'


def author_only_path(method: str,path: str) -> bool:
    return method=='POST' and bool(_AUTHOR_ONLY.match(path))


def guard_bridge_run(request,run_request) -> None:
    """MCP-BRIDGE-S49/S51: the bridge starts one stage or a card suggestion, only in a story Obscura writes, and (R-44 PR 4)
    an audit of links in either mode: the auditor writes no story text, and a character search in either mode with the plan fingerprint. R-48 PR 2: a memory build (its cost grows with the
    book) also needs the plan fingerprint the author saw, so the consent rule is backed on the server."""
    if not from_bridge(request):return
    if run_request.mode not in BRIDGE_RUN_MODES:raise BridgeForbidden(RUN_OWNER_ONLY)
    if run_request.mode=='audit':return
    if run_request.mode=='character_extract':
        # R-51: the search writes no text of the book (a proposal the author accepts later), so either mode; the plan is the consent.
        if run_request.extract_plan_fingerprint is None:raise RevisionConflict(EXTRACT_PLAN_REQUIRED)
        return
    if request.app.state.repo.get_story(run_request.story_id).writing_mode!='obscura':raise RevisionConflict(CHAT_WRITES)
    if run_request.mode=='rebuild_memory' and run_request.memory_plan_fingerprint is None:raise RevisionConflict(MEMORY_PLAN_REQUIRED)


def guard_bridge_cast(request,story_id: str) -> None:
    """R-48 review M-9: the scene casts from the names in the prose are written only as the first step of a memory build,
    so the bridge may write them in the same stories it may start that build in (`guard_bridge_run`)."""
    if from_bridge(request) and request.app.state.repo.get_story(story_id).writing_mode!='obscura':raise RevisionConflict(CHAT_WRITES)


def guard_bridge_cancel(request,run) -> None:
    if from_bridge(request) and run.origin!='mcp':raise BridgeForbidden(RUN_OWNER_ONLY)


def require_writable_by_chat(repo,story_id: str) -> None:
    if repo.get_story(story_id).writing_mode=='obscura':
        raise RevisionConflict(OBSCURA_WRITES)


def guard_scene_write(request,scene_id: str) -> None:
    """Only bridge requests are checked: the author writes in any mode."""
    if from_bridge(request):
        repo=request.app.state.repo
        require_writable_by_chat(repo,repo.active_scene_story_id(scene_id))
