"""WRITING-MODE: requests from the MCP bridge carry a header; the story mode decides what the chat may write."""
from ..domain import RevisionConflict

BRIDGE_HEADER='X-Obscura-Client'
OBSCURA_WRITES='Твір у режимі «пише Obscura»: чат не записує тексти — запустіть етап в Obscura'
MODE_OWNER_ONLY='Режим твору змінює лише автор в Obscura'


class BridgeForbidden(Exception):
    """An action the bridge may never take; the app answers 403 with a localized detail."""


def from_bridge(request) -> bool:
    return request.headers.get(BRIDGE_HEADER)=='mcp'


def require_writable_by_chat(repo,story_id: str) -> None:
    if repo.get_story(story_id).writing_mode=='obscura':
        raise RevisionConflict(OBSCURA_WRITES)


def guard_scene_write(request,scene_id: str) -> None:
    """Only bridge requests are checked: the author writes in any mode."""
    if from_bridge(request):
        repo=request.app.state.repo
        require_writable_by_chat(repo,repo.active_scene_story_id(scene_id))
