"""Spec 2026-11-17-broken-letters-guard: reactions to new U+FFFD by stage category."""
import json

import pytest
import threading

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository
from tests.generation.test_editor_output import run_output
from tests.memory.wire_helpers import v4_answer
from tests.link_helpers import approve_links

R = '�'


class Gateway:
    def __init__(self, raw):
        self.raw = raw

    def stream(self, *_):
        yield GenerationEvent(type='delta', text=self.raw)
        yield GenerationEvent(type='terminal', finish_reason='stop')


def memory_case(tmp_path, prose):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Журнал'))
    scene = repo.create_scene(story.id, SceneCreate(title='1', character_ids=['A']))
    ref = repo.save_version(story.id, scene.id, 'manual', prose, [])
    repo.set_head(scene.id, 'prose', ref.id, scene.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='evidence_delta', context_tokens=32768)
    return repo, scene, build_context(repo, scene.id, 'memory', role)


def run_memory(repo, scene, context, text):
    item = {'text': text, 'evidence_ids': ['f000001'], 'character_ids': ['A']}
    raw = v4_answer(context, character_states_add=[item])
    return execute_stage(repo, scene.id, 'memory', context, Gateway(raw), threading.Event(), lambda _: None)


def test_memory_with_new_broken_word_fails_without_a_version(tmp_path):
    repo, scene, context = memory_case(tmp_path, 'A сидів у бібліотеці, готуючи знімки.')
    attempt = run_memory(repo, scene, context, f'A у бібл{R}{R}отеці')
    assert attempt.state == 'failed'
    assert attempt.result_version_id is None
    assert attempt.context['generation_failure']['category'] == 'broken_output'
    assert 'бібл' not in attempt.error and '1' in attempt.error
    assert not repo.get_scene(scene.id).heads.get('memory')


def test_memory_copying_an_old_broken_word_is_saved(tmp_path):
    repo, scene, context = memory_case(tmp_path, f'A сидів у бібл{R}{R}отеці, готуючи знімки.')
    attempt = run_memory(repo, scene, context, f'A у бібл{R}{R}отеці')
    assert attempt.state == 'completed', attempt.error


def test_diff_drops_only_the_broken_edit(tmp_path):
    raw = f'Олена ч{R}{R}кала два тижні. Це не ваша провина.'
    repo, scene, attempt = run_output(tmp_path, raw, 'diff')
    assert attempt.state == 'needs_review', attempt.error
    proposal = attempt.context['copyedit_proposal']['proposal']
    assert [edit['replacement'] for edit in proposal['edits']] == ['ваша']
    assert R not in proposal['candidate_text']
    assert any('«�»' in warning for warning in attempt.context['editor_warnings'])


def test_diff_with_only_broken_edits_has_no_changes(tmp_path):
    repo, scene, attempt = run_output(tmp_path, f'Олена ч{R}{R}кала два тижні. Це не ваші провина.', 'diff')
    assert attempt.state == 'failed'
    assert attempt.context['editor_failure']['category'] == 'no_changes'
    assert not attempt.context.get('copyedit_proposal')


def test_patches_drop_only_the_broken_edit(tmp_path):
    raw = json.dumps({'edits': [
        dict(fragment_id='f000001', original='чекала', replacement=f'ч{R}{R}кала', category='grammar'),
        dict(fragment_id='f000001', original='ваші', replacement='ваша', category='grammar'),
    ]}, ensure_ascii=False)
    repo, scene, attempt = run_output(tmp_path, raw, 'patches')
    assert attempt.state == 'needs_review', attempt.error
    assert [edit['replacement'] for edit in attempt.context['copyedit_proposal']['proposal']['edits']] == ['ваша']
    assert any('«�»' in warning for warning in attempt.context['editor_warnings'])


def draft_case(tmp_path, previous=''):
    from tests.generation.test_evidence_protocols import seeded
    repo, scene = seeded(tmp_path)
    if previous:
        ref = repo.save_version(scene.story_id, scene.id, 'draft', previous, [])
        scene = repo.set_head(scene.id, 'draft', ref.id, scene.revision)
    brief = repo.save_version(scene.story_id, scene.id, 'brief', '{"objective":"Чекання","beats":["Зателефонувати"]}', [])
    scene = repo.set_head(scene.id, 'brief', brief.id, scene.revision)
    approve_links(repo, scene.story_id)
    return repo, scene, build_context(repo, scene.id, 'draft', RoleSettings(provider=ProviderSettings(model='fake')))


def test_draft_is_saved_with_a_count_only_warning(tmp_path):
    repo, scene, context = draft_case(tmp_path)
    raw = f'Олена ч{R}{R}кала два тижні.'
    attempt = execute_stage(repo, scene.id, 'draft', context, Gateway(raw), threading.Event(), lambda _: None)
    assert attempt.result_version_id, attempt.error
    assert repo.read_text(attempt.result_version_id) == raw
    assert attempt.context['broken_text_warnings'] == ['У тексті слів із символом «�»: 1. Виправте їх у редакторі.']


def test_clean_draft_has_no_warning(tmp_path):
    repo, scene, context = draft_case(tmp_path)
    attempt = execute_stage(repo, scene.id, 'draft', context, Gateway('Олена чекала два тижні.'), threading.Event(), lambda _: None)
    assert attempt.result_version_id, attempt.error
    assert 'broken_text_warnings' not in attempt.context


def test_rewrite_drops_broken_edits_and_reports_them(rewrite_case):
    from storygen.generation.assisted_writing import build_rewrite_context
    from storygen.generation.rewrite_review import rewrite_preview
    repo, scene, source, notes, role, request = rewrite_case
    raw = f'Вечір був **тих{R}{R}м**. Вона поспішала додому.'
    attempt = execute_stage(repo, scene.id, 'rewrite', build_rewrite_context(repo, request), Gateway(raw),
                            threading.Event(), lambda _: None)
    assert attempt.state == 'needs_review', attempt.error
    edits = attempt.context['rewrite_proposal']['proposal']['edits']
    assert all(R not in edit['replacement'] for edit in edits) and edits
    assert rewrite_preview(repo, scene.id, attempt.id)['warnings'] == attempt.context['rewrite_warnings']


def test_memory_copying_a_broken_one_letter_word_is_saved(tmp_path):
    repo, scene, context = memory_case(tmp_path, f'A сидів {R}{R} бібліотеці, готуючи знімки.')
    attempt = run_memory(repo, scene, context, f'A сидить {R}{R} бібліотеці')
    assert attempt.state == 'completed', attempt.error


def test_classifier_with_a_new_broken_word_fails_with_its_own_category(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import RunRequest
    from tests.generation.test_edit_classification import fixture
    repo, scene, proposal = fixture(tmp_path)
    preview = copyedit_preview(repo, scene.id, proposal.id)
    raw = json.dumps({'items': [{'index': 0, 'category': 'grammar', 'note': f'зм{R}{R}на'}]}, ensure_ascii=False)
    worker = RunCoordinator(repo, gateway_factory=lambda _: Gateway(raw))
    request = RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='classify', proposal_attempt_id=proposal.id,
                         proposal_fingerprint=preview['proposal_fingerprint'])
    run = worker.enqueue(request, 'broken')
    run.state = 'running'
    repo.save_run(run)
    worker._execute(run.id)
    attempt = repo.list_attempts(scene.story_id, run.id)[0]
    assert attempt.state == 'failed'
    assert attempt.context['classification_failure']['category'] == 'broken_output'


@pytest.mark.parametrize('mode', ['patches', 'diff'])
def test_editor_loop_pass_with_only_broken_edits_stops_as_no_changes(tmp_path, mode):
    from tests.generation.test_editor_loop import SOURCE, patch, seeded
    broken = patch('йшов', f'й{R}{R}ла') if mode == 'patches' else SOURCE.replace('йшов', f'й{R}{R}ла')
    repo, scene, draft, worker, run, calls = seeded(tmp_path, [broken], mode=mode)
    worker._execute(run.id)
    current = worker.get_run(run.id)
    assert current.editor_loop['stop_reason'] == 'no_changes' and len(calls) == 1
    assert 'Відкинуто правок із пошкодженими літерами «�»: 1.' in current.warning


@pytest.mark.parametrize('mode', ['patches', 'diff'])
def test_editor_loop_summary_reports_dropped_edits(tmp_path, mode):
    from storygen.generation.copyedit_review import copyedit_preview
    from tests.generation.test_editor_loop import SOURCE, seeded
    two = json.dumps({'edits': [dict(fragment_id='f000001', original='йшов', replacement='йшла', category='grammar'),
                                dict(fragment_id='f000001', original='тихо', replacement=f'ти{R}{R}', category='grammar')]},
                     ensure_ascii=False)
    first = two if mode == 'patches' else SOURCE.replace('йшов', 'йшла').replace('тихо', f'ти{R}{R}')
    done = '{"edits":[]}' if mode == 'patches' else SOURCE.replace('йшов', 'йшла')
    repo, scene, draft, worker, run, calls = seeded(tmp_path, [first, done], mode=mode)
    worker._execute(run.id)
    current = worker.get_run(run.id)
    assert current.state == 'needs_review', current.error
    preview = copyedit_preview(repo, scene.id, current.editor_loop['proposal_attempt_id'])
    assert R not in preview['preview']
    assert any('«�»' in warning for warning in preview['warnings'])
