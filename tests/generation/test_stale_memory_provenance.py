import threading

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.dependencies import invalidate_dependents
from storygen.generation.stages import execute_stage
from storygen.memory.models import MemorySnapshot
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository


def workspace(tmp_path, already_stale):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пам’ять і походження'))
    first = repo.create_scene(story.id, SceneCreate(title='Перша'))
    current = repo.create_scene(story.id, SceneCreate(title='Друга', beats='Новий день'))
    root = repo.save_version(story.id, first.id, 'draft', 'Чернетка першої.', [])
    prose = repo.save_version(story.id, first.id, 'edited', 'Події першої сцени.', [root.id])
    first = repo.set_head(first.id, 'prose', prose.id, first.revision)
    if already_stale:
        invalidate_dependents(repo, [root.id])
    snapshot = MemorySnapshot(source_prose_ids=[prose.id])
    memory = repo.save_version(story.id, first.id, 'memory', snapshot.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, first.revision)
    brief = repo.save_version(story.id, current.id, 'brief', '{"objective":"День","beats":[],"constraints":[],"proposed_changes":[]}', [])
    repo.set_head(current.id, 'brief', brief.id, current.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake'))
    return repo, current, root, prose, memory, role


@pytest.mark.parametrize('stage', ['brief', 'draft'])
def test_existing_stale_prose_with_current_verified_memory_does_not_cause_false_conflict(tmp_path, stage):
    repo, scene, root, prose, memory, role = workspace(tmp_path, already_stale=True)
    context = build_context(repo, scene.id, stage, role)
    class Gateway:
        def stream(self, context, cancel):
            text = '{"objective":"День","beats":["Ранок"],"constraints":[],"proposed_changes":[]}' if stage == 'brief' else 'Нова чернетка.'
            yield GenerationEvent(type='delta', text=text)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, stage, context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    assert repo.get_scene(scene.id).heads[stage] == attempt.result_version_id
    assert repo.get_version(prose.id).stale, 'using a verified memory does not mark its prose as reviewed'


def test_source_becoming_stale_during_generation_still_causes_conflict(tmp_path):
    repo, scene, root, prose, memory, role = workspace(tmp_path, already_stale=False)
    context = build_context(repo, scene.id, 'draft', role)
    class Gateway:
        def stream(self, context, cancel):
            yield GenerationEvent(type='delta', text='Альтернативна чернетка.')
            invalidate_dependents(repo, [root.id])
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, 'draft', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'alternative'
    assert 'draft' not in repo.get_scene(scene.id).heads
