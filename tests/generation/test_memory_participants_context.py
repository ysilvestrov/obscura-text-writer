"""MEMORY-ENTITIES-S01: the memory request lists every character card as an allowed participant."""
import json

import pytest

from storygen.generation.context import build_context
from storygen.generation.memory_build import SECTION_CATEGORIES
from tests.generation.test_character_names_context import role, setup
from tests.generation.test_location_context import memory_scene
from tests.generation.test_location_context import role as plain_role

HEAD = 'ДОЗВОЛЕНІ PARTICIPANT_IDS'


def section(context):
    return next(part for part in context.user_text.split('\n\n') if part.startswith(HEAD))


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_request_lists_every_card_as_allowed_participants(tmp_path):
    from storygen.domain import SceneCreate
    repo, scenes = setup(tmp_path)
    # the scene cast is the second card only; the first card stays outside it but remains allowed
    repo.update_scene_metadata(scenes[0].id, {'character_ids': ['h']}, scenes[0].revision)
    scene = repo.get_scene(scenes[0].id)
    prose = repo.save_version(scene.story_id, scene.id, 'manual', 'Хазяїн мовчав.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    context = build_context(repo, scene.id, 'memory', role())
    names = json.loads(section(context).split('\n', 1)[1])
    assert set(names) == {'j', 'h'} and names['j'] == 'Юлія'
    assert json.loads(context.fragments['memory_schema_bounds'])['participant_ids'] == ['j', 'h']


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_request_without_cards_is_unchanged(tmp_path):
    repo, story, scene = memory_scene(tmp_path, 'Вдома')
    context = build_context(repo, scene.id, 'memory', plain_role())
    assert 'PARTICIPANT_IDS' not in context.user_text
    assert 'participant_ids' not in context.fragments['memory_schema_bounds']


@pytest.mark.req('MEMORY-ENTITIES')
def test_sends_cover_participants_section():
    assert SECTION_CATEGORIES['allowed_participant_ids'] == 'memory_catalog'
