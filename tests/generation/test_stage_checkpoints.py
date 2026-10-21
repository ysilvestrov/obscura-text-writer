import json
import os
import subprocess
import sys
import threading

import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository


def setup_stage(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Checkpoint'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Ранок'))
    role = RoleSettings(provider=ProviderSettings(model='offline'))
    save_role_settings(repo, story.id, 'planner', role, repo.get_story(story.id).revision)
    context = build_context(repo, scene.id, 'brief', role)
    return repo, scene, context


@pytest.mark.parametrize('ending', ['stop', 'cancel', 'error', 'exception'])
def test_stage_checkpoints_flush_before_final_state(tmp_path, ending):
    repo, scene, context = setup_stage(tmp_path)
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='stage', stage='brief'), ending)
    text = json.dumps({'objective': 'а' * 10000, 'beats': ['Ранок']}, ensure_ascii=False)
    cancel = threading.Event()
    class Gateway:
        def stream(self, context, cancel):
            for start in range(0, len(text), 10):
                yield GenerationEvent(type='delta', text=text[start:start + 10])
            if ending == 'exception':
                raise RuntimeError('provider failure with private payload')
            if ending == 'cancel':
                cancel.set()
            yield GenerationEvent(type={'stop': 'terminal', 'cancel': 'cancelled', 'error': 'error'}[ending], finish_reason='stop' if ending == 'stop' else None)
    def on_delta(batch):
        attempt = repo.list_attempts(scene.story_id, run.id)[0]
        persisted = repo.files.resolve(attempt.partial_path).read_text(encoding='utf-8')
        prior = ''.join(e.data['text'] for e in worker.list_events(run.id) if e.type == 'delta')
        assert persisted == prior + batch  # Disk is complete before SQL event is published.
        assert attempt.state == 'running'
        worker.event(run.id, 'delta', {'text': batch, 'stage': 'brief', 'scene_id': scene.id})
    if ending == 'exception':
        with pytest.raises(RuntimeError):
            execute_stage(repo, scene.id, 'brief', context, Gateway(), cancel, on_delta, run.id)
        attempt = repo.list_attempts(scene.story_id, run.id)[0]
        assert 'private payload' not in attempt.error
    else:
        attempt = execute_stage(repo, scene.id, 'brief', context, Gateway(), cancel, on_delta, run.id)
    batches = [e for e in worker.list_events(run.id) if e.type == 'delta']
    assert ''.join(e.data['text'] for e in batches) == text
    assert len(batches) < 10
    assert repo.files.resolve(attempt.partial_path).read_text(encoding='utf-8') == text
    assert attempt.state == {'stop': 'completed', 'cancel': 'cancelled', 'error': 'failed', 'exception': 'failed'}[ending]
    if ending != 'stop':
        assert not repo.get_scene(scene.id).heads.get('brief')
        assert not attempt.result_version_id


@pytest.mark.parametrize('failure', ['disk', 'event'])
def test_checkpoint_failure_never_publishes_result(tmp_path, monkeypatch, failure):
    repo, scene, context = setup_stage(tmp_path)
    class Gateway:
        def stream(self, context, cancel):
            if failure == 'disk':
                def fail_sync(fd):
                    raise OSError('disk failure')
                monkeypatch.setattr(os, 'fsync', fail_sync)
            yield GenerationEvent(type='delta', text='{"objective":"Ранок","beats":["x"]}')
            yield GenerationEvent(type='terminal', finish_reason='stop')
    def on_delta(text):
        raise RuntimeError('SQL event failed')
    with pytest.raises((OSError, RuntimeError)):
        execute_stage(repo, scene.id, 'brief', context, Gateway(), threading.Event(), on_delta)
    attempt = repo.list_attempts(scene.story_id)[0]
    assert attempt.state == 'failed' and not attempt.result_version_id
    assert not repo.get_scene(scene.id).heads.get('brief')


def test_abrupt_process_exit_keeps_only_prior_checkpoint(tmp_path):
    script = '''
import os, sys
from storygen.storage.files import FileStore
from storygen.generation.stream_buffer import StreamBuffer
store = FileStore(__import__('pathlib').Path(sys.argv[1]))
with StreamBuffer(store.open_partial('partial.txt'), lambda text: None, clock=lambda: 0) as buffer:
    buffer.append('Довговічний checkpoint')
    buffer.flush()
    buffer.append('Незбережений хвіст')
    os._exit(0)
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'partial.txt').read_text(encoding='utf-8') == 'Довговічний checkpoint'
