import json
import threading

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.storage.repository import Repository


def test_fragments_are_exact_deterministic_and_do_not_join_dialogue():
    from storygen.generation.evidence import fragment_text
    text = "— Що обрала я? — запитала вона. — Студію.\n\nДвері відчинені."
    fragments = fragment_text(text)
    assert fragments == fragment_text(text)
    assert all(text[f.start:f.end] == f.text for f in fragments)
    assert len({f.id for f in fragments}) == len(fragments)
    assert any('запитала вона' in f.text for f in fragments)


def test_memory_delta_resolves_quotes_and_retains_previous_without_model_copy():
    from storygen.generation.evidence import fragment_text
    from storygen.memory.models import MemoryDelta, MemoryEntry, MemorySnapshot
    from storygen.memory.service import merge_memory_delta
    old = MemoryEntry(text='Затримка ремонту.', source_version_id='old', quote='два тижні')
    previous = MemorySnapshot(facts=[old], source_prose_ids=['old'])
    prose = 'Олена відчинила двері.\n\nЛана чекала у бібліотеки.'
    fragments = fragment_text(prose)
    delta = MemoryDelta.model_validate({'facts': [{'text': 'Лана у бібліотеки.', 'evidence_id': fragments[1].id}]})
    result = merge_memory_delta(previous, delta, 'new', prose)
    assert result.facts[0] == old and result.source_prose_ids == ['old', 'new']
    assert result.facts[-1].quote == 'Лана чекала у бібліотеки.'
    assert result.facts[-1].source_version_id == 'new'
    with pytest.raises(ValueError):
        merge_memory_delta(previous, MemoryDelta.model_validate({'facts': [{'text': 'Вигадка', 'evidence_id': 'absent'}]}), 'new', prose)


def test_copyedit_patches_are_anchored_nonoverlapping_and_preserve_numbers():
    from storygen.generation.evidence import fragment_text
    from storygen.generation.copyediting import CopyEdits, apply_copyedits
    text = 'Олена чекала два тижні. Це не ваші провина.\n\nЛана прийшла.'
    id = fragment_text(text)[0].id
    def edits(*items):
        return CopyEdits.model_validate({'edits': [{'fragment_id': id, 'original': a, 'replacement': b, 'category': 'grammar'} for a, b in items]})
    assert apply_copyedits(text, edits(('ваші', 'ваша'))) == text.replace('ваші', 'ваша')
    for patch in [edits(('два', 'три')), edits(('немає', 'є')), edits(('ваші', 'ваша'), ('ваші', 'інша'))]:
        with pytest.raises(ValueError):
            apply_copyedits(text, patch)
    with pytest.raises(ValueError):
        apply_copyedits('Олена прийшла.', CopyEdits.model_validate({'edits': [{'fragment_id': 'f000001', 'original': 'Олена прийшла.', 'replacement': 'Лана пішла.', 'category': 'grammar'}]}))


def test_copyedits_cannot_silently_remove_negation_or_expand_to_a_rewrite():
    from storygen.generation.copyediting import CopyEdits, apply_copyedits
    text = 'Олена не погодилась. Вона чекала спокійно й мовчки.'
    for original, replacement in [('не погодилась', 'погодилась'), ('чекала', 'довго чекала у бібліотеки й вирішила зателефонувати підрядникові')]:
        proposal = CopyEdits.model_validate({'edits': [{'fragment_id': 'f000001', 'original': original, 'replacement': replacement, 'category': 'wording'}]})
        with pytest.raises(ValueError):
            apply_copyedits(text, proposal)


def test_partial_word_patch_cannot_bypass_number_and_negation_guards():
    from storygen.generation.copyediting import CopyEdits, apply_copyedits
    for text, original, replacement in [('Вона чекала два тижні у бібліотеки.', 'ва тижні', 'ві тижні'), ('Олена не пішла, залишилась у бібліотеки.', 'е п', ' п')]:
        proposal = CopyEdits.model_validate({'edits': [{'fragment_id': 'f000001', 'original': original, 'replacement': replacement, 'category': 'grammar'}]})
        with pytest.raises(ValueError):
            apply_copyedits(text, proposal)


def test_invalid_editor_patch_keeps_original_draft_and_partial_response(tmp_path):
    repo, scene = seeded(tmp_path)
    role = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches')
    context = build_context(repo, scene.id, 'edit', role)
    raw = json.dumps({'edits': [{'fragment_id': 'f000001', 'original': 'два', 'replacement': 'три', 'category': 'wording'}]})
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, 'edit', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'failed' and 'prose' not in repo.get_scene(scene.id).heads
    assert 'два тижні' in repo.read_text(scene.heads['draft'])
    assert repo.files.resolve(attempt.partial_path).read_text(encoding='utf-8') == raw


def seeded(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Тест'))
    scene = repo.create_scene(story.id, SceneCreate(title='Студія', beats='Зателефонувати адміністратору.'))
    ref = repo.save_version(story.id, scene.id, 'draft', 'Олена чекала два тижні. Це не ваші провина.', [])
    repo.set_head(scene.id, 'draft', ref.id, scene.revision)
    return repo, repo.get_scene(scene.id)


def test_patch_editor_context_excludes_plan_and_publishes_only_applied_prose(tmp_path):
    from storygen.generation.evidence import fragment_text
    repo, scene = seeded(tmp_path)
    role = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches')
    context = build_context(repo, scene.id, 'edit', role)
    assert 'Зателефонувати адміністратору' not in context.user_text
    assert 'МАЙБУТНІ ПОДІЇ' not in context.user_text
    id = fragment_text(repo.read_text(scene.heads['draft']))[0].id
    raw = json.dumps({'edits': [{'fragment_id': id, 'original': 'ваші', 'replacement': 'ваша', 'category': 'grammar'}]}, ensure_ascii=False)
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, 'edit', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    assert repo.read_text(attempt.result_version_id).endswith('Це не ваша провина.')
    assert repo.files.resolve(attempt.partial_path).read_text(encoding='utf-8') == raw


def test_evidence_memory_context_and_stage_publish_compatible_snapshot(tmp_path):
    repo, scene = seeded(tmp_path)
    prose = repo.save_version(scene.story_id, scene.id, 'edited', 'Олена відчинила двері.', [scene.heads['draft']])
    repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='evidence_delta')
    context = build_context(repo, scene.id, 'memory', role)
    assert 'f000001' in context.user_text
    raw = json.dumps({'facts': [{'text': 'Олена відчинила двері.', 'evidence_id': 'f000001'}]})
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    attempt = execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    result = json.loads(repo.read_text(attempt.result_version_id))
    assert result['schema_version']==2
    assert result['events'][0]['quote'] == 'Олена відчинила двері.'
    assert result['source_prose_ids'] == [prose.id]


def test_three_scenes_accumulate_evidence_deltas_without_echoing_old_facts(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator, RunRequest
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Три сцени'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i}',beats=f'Подія {i}')) for i in range(3)]
    for role in ('planner', 'writer', 'editor', 'memory'):
        settings = RoleSettings(provider=ProviderSettings(model=role), edit_mode='patches', memory_mode='evidence_delta')
        save_role_settings(repo, story.id, role, settings, repo.get_story(story.id).revision)
    class Gateway:
        def stream(self, context, _):
            position = repo.get_scene(context.scene_id).position
            raw = {
                'brief': json.dumps({'objective': 'Сцена', 'beats': ['Подія']}),
                'draft': f'Олена відчинив двері номер {position}.',
                'edit': json.dumps({'edits':[dict(fragment_id='f000001',original='відчинив',replacement='відчинила',category='grammar')]}),
                'memory': json.dumps({'facts': [{'text': f'Подія {position}.', 'evidence_id': 'f000001'}]}),
            }[context.stage]
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    worker = RunCoordinator(repo, gateway_factory=lambda _: Gateway())
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[0].id, mode='remaining'), 'three-evidence')
    worker._execute(run.id)
    assert worker.get_run(run.id).state == 'completed'
    last = repo.get_scene(scenes[-1].id)
    snapshot = json.loads(repo.read_text(last.heads['memory']))
    assert len(snapshot['events']) == len(snapshot['source_prose_ids']) == 3
    assert [e['quote'] for e in snapshot['events']] == [f'Олена відчинила двері номер {i}.' for i in range(3)]
