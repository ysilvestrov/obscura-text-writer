"""MEMORY-SUMMARY API (#68): blocks of timeline summaries, readiness of a rebuild and the author's correction."""
from fastapi import APIRouter, Request
from pydantic import Field

from ..domain import DomainModel

router = APIRouter()


class SummaryCorrection(DomainModel):
    text: str = Field(max_length=4000)
    expected_version_id: str = Field(min_length=1, max_length=64)
    expected_revision: int


def summaries_view(repo, story_id: str) -> dict:
    from ..generation.timeline_summary import block_inputs
    from ..memory.summaries import block_state
    from ..memory.summary_blocks import recommended, summary_blocks
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    scenes = view.list_scenes(story_id)
    with_memory = [n for n, s in enumerate(sorted(scenes, key=lambda s: s.position), 1) if s.heads.get('memory')]
    last = max(with_memory, default=0)
    blocks = []
    for block in summary_blocks(story, scenes):
        state, reason, payload = block_state(view, story, scenes, block)
        try:
            block_inputs(view, story, scenes, block)
            ready, ready_reason = True, None
        except ValueError as exc:
            ready, ready_reason = False, str(exc)
        blocks.append({'key': block.key, 'title': block.title, 'part': block.part, 'first_number': block.first_number,
                       'last_number': block.last_number, 'state': state, 'reason': reason,
                       'recommended': ready and state != 'fresh' and recommended(block, last), 'ready': ready, 'ready_reason': ready_reason,
                       'text': payload.get('text') if payload else None, 'origin': payload.get('origin') if payload else None,
                       'version_id': story.timeline_summary_heads.get(block.key)})
    return {'story_revision': story.revision, 'blocks': blocks}


@router.get('/api/stories/{story_id}/timeline-summaries')
def list_summaries(story_id: str, request: Request):
    return summaries_view(request.app.state.repo, story_id)


@router.get('/api/stories/{story_id}/timeline-summaries/readiness')
def summary_readiness(story_id: str, block_key: str, request: Request):
    from ..generation.readiness import preview
    from ..run_models import RunRequest
    return preview(request.app.state.repo, RunRequest(story_id=story_id, mode='timeline_summary', summary_block_key=block_key))


@router.put('/api/stories/{story_id}/timeline-summaries/{block_key}')
def correct_summary(story_id: str, block_key: str, change: SummaryCorrection, request: Request):
    from ..storage.timeline_summaries import save_author_summary
    repo = request.app.state.repo
    save_author_summary(repo, story_id, block_key, change.text, change.expected_version_id, change.expected_revision)
    return summaries_view(repo, story_id)
