"""WRITING-MODE (R-49): in a story in the «Пишу сам» mode (`writing_mode='author'`) no model writes or applies prose.

One list says which runs write prose; the checks in `RunCoordinator.enqueue`, `execute_stage`, the proposal-apply routes and
the external-text routes read it, so a new run mode without a decision fails `test_every_run_mode_has_a_prose_decision`."""

AUTHOR_WRITES='Твір у режимі «Пишу сам»: модель не пише прозу. Змініть режим у налаштуваннях твору'
AUTHOR_CHAT='Твір у режимі «Пишу сам»: прозу пише автор'

# Stages of `execute_stage` whose result is prose or a prose proposal: the draft, the editor (every edit mode, the copyedit
# proposals included, owner decision 26.11.2026) and the rewrite of the author's comments.
PROSE_STAGES=frozenset({'draft','edit','rewrite'})

# Every RunRequest.mode: True writes prose, False does not, None is decided by the stage (brief and memory do not write).
RUN_MODE_WRITES: dict[str,bool|None]={
    'stage':None,'scene':True,'remaining':True,'edit_loop':True,'rewrite':True,
    'prepare':False,'rebuild_memory':False,'memory_carry':False,'evaluate':False,'classify':False,'publication_suggest':False,
    'timeline_summary':False,'audit':False,'character_extract':False,
    'impact':False,  # removed (R-44 PR 1): Worker.enqueue refuses it anyway
}


class AuthorWritesBlocked(ValueError):
    """A model step that would write prose in a story in the «Пишу сам» mode; the run fails with this message."""


def writes_prose(request) -> bool:
    decision=RUN_MODE_WRITES[request.mode]
    return request.stage in PROSE_STAGES if decision is None else decision


def is_author(repo,story_id: str) -> bool:
    return repo.get_story(story_id).writing_mode=='author'
