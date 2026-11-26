"""R-49: the «Пишу сам» story mode (`writing_mode='author'`): models never write or apply prose. Neutral texts, no provider."""
from typing import get_args

import pytest

from storygen.run_models import RunRequest
from storygen.writing_mode import RUN_MODE_WRITES, writes_prose
from tests.web.test_chat_stage_routes import app_with_scene


@pytest.mark.req('WRITING-MODE')
def test_every_run_mode_has_a_prose_decision():
    assert set(RUN_MODE_WRITES) == set(get_args(RunRequest.model_fields['mode'].annotation))


WRITING = [('stage', 'draft'), ('stage', 'edit'), ('scene', None), ('remaining', None), ('edit_loop', None), ('rewrite', None)]
NOT_WRITING = [('stage', 'brief'), ('stage', 'memory'), ('prepare', None), ('rebuild_memory', None), ('memory_carry', None),
               ('evaluate', None), ('audit', None), ('character_extract', None), ('classify', None),
               ('publication_suggest', None), ('timeline_summary', None)]


@pytest.mark.req('WRITING-MODE')
def test_writes_prose_by_mode_and_stage():
    for mode, stage in WRITING:
        assert writes_prose(RunRequest.model_construct(story_id='s', mode=mode, stage=stage)), (mode, stage)
    for mode, stage in NOT_WRITING:
        assert not writes_prose(RunRequest.model_construct(story_id='s', mode=mode, stage=stage)), (mode, stage)


@pytest.mark.req('WRITING-MODE')
def test_author_mode_is_accepted_at_creation_and_switch(tmp_path):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=False)
    created = client.post('/api/stories', json={'title': 'Сад', 'writing_mode': 'author'})
    assert created.status_code == 200, created.text
    assert created.json()['writing_mode'] == 'author'
    story = repo.get_story(story.id)
    changed = client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': 'author', 'expected_revision': story.revision})
    assert changed.status_code == 200, changed.text
    assert repo.get_story(story.id).writing_mode == 'author' and repo.get_story(story.id).revision == story.revision + 1
