"""CHARACTER-EXTRACT (R-51): the run preview, its fingerprint and the queue guards of the `character_extract` mode."""
from decimal import Decimal

import pytest

from storygen.authoring.blueprints import get_role_settings
from storygen.billing.models import Tariff
from storygen.billing.service import save_tariff, set_limit
from storygen.characters.extract_plan import (
    EXTRACT_PLAN_CHANGED, EXTRACT_RUNNING, NO_FINISHED_PROSE, NO_PROSE, PENDING_PROPOSAL, extract_plan)
from storygen.domain import RevisionConflict
from storygen.generation.audit_cost import upper_bound
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.extract_context import NO_MEMORY_ROLE, resolve_extractor
from storygen.generation.readiness import pending_preview, preview
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.run_models import RunRequest
from tests.generation.test_memory_build import OPENROUTER, tariff, with_cards, written_book

WORDS = ' '.join(['слово'] * 600) + '.'


def local_role(**limits):
    return RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=32768, **limits)


def cloud_role(**limits):
    return RoleSettings(provider=ProviderSettings(provider='openrouter', model='cloud-model'), context_tokens=32768,
                        max_input_chars=limits.pop('max_input_chars', 20000), max_output_tokens=1000, **limits)


def request(story, **extra):
    return RunRequest(story_id=story.id, mode='character_extract', **extra)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_preview_counts_groups_calls_cost(tmp_path):
    repo, story, scenes = written_book(tmp_path, [WORDS] * 3, memory_role=cloud_role())
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    plan = extract_plan(repo, story.id, 1000)
    assert plan['ready'] is True, plan['reason']
    assert plan['groups'] == [[s.id] for s in scenes]  # 600 + 600 words exceed the 1000 words budget
    assert (plan['scenes_count'], plan['calls_bound'], plan['skipped']) == (3, 8, [])
    assert plan['cost'] == upper_bound(repo, resolve_extractor(get_role_settings(repo, story.id)), 8)
    assert plan['cost']['total_usd'] is not None and len(plan['plan_fingerprint']) == 64
    assert extract_plan(repo, story.id, 5000)['groups'] == [[s.id for s in scenes]]
    assert (plan['cards_count'], plan['has_protagonist'], plan['pending_proposal']) == (0, False, False)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_local_preview_is_free_and_cloud_needs_a_limit(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=local_role())
    plan = extract_plan(repo, story.id)
    assert plan['ready'] is True and plan['cost']['total_usd'] is None and plan['calls_bound'] == 4
    repo, story, _ = written_book(tmp_path / 'cloud', [WORDS], memory_role=cloud_role())
    refused = extract_plan(repo, story.id)
    assert refused['ready'] is False and refused['reason'] == 'Спершу задайте явний ліміт бюджету в налаштуваннях'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_preview_skips_scenes_without_prose(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['', WORDS], memory_role=local_role())
    plan = extract_plan(repo, story.id)
    assert plan['groups'] == [[scenes[1].id]] and plan['scenes_count'] == 1
    assert plan['skipped'] == [{'scene_id': scenes[0].id, 'reason': NO_FINISHED_PROSE}]
    repo, story, _ = written_book(tmp_path / 'none', ['', ''], memory_role=local_role())
    empty = extract_plan(repo, story.id)
    assert empty['ready'] is False and empty['reason'] == NO_PROSE and empty['groups'] == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unfit_scene_is_skipped_with_the_reason(tmp_path):
    repo, story, scenes = written_book(tmp_path, [WORDS, 'Мала.'], memory_role=local_role(max_input_chars=3000))
    save_manual_prose(repo, scenes[0].id, ' '.join(['слово'] * 2000), repo.get_scene(scenes[0].id).revision)
    plan = extract_plan(repo, story.id)
    assert plan['groups'] == [[scenes[1].id]]
    assert plan['skipped'] == [{'scene_id': scenes[0].id, 'reason': "не вміщується в ліміт входу ролі «Пам'ять»"}]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_realistic_context_fits_one_ukrainian_scene(tmp_path):
    role = lambda tokens: RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=tokens)
    repo, story, scenes = written_book(tmp_path, [WORDS], memory_role=role(32768))
    plan = extract_plan(repo, story.id)
    assert plan['ready'] is True and plan['groups'] == [[scenes[0].id]]
    repo, story, scenes = written_book(tmp_path / 'small', [WORDS], memory_role=role(8192))
    small = extract_plan(repo, story.id)
    assert small['ready'] is False and small['groups'] == []
    context_reason = "не вміщується в контекст ролі «Пам'ять»"
    assert small['skipped'] == [{'scene_id': scenes[0].id, 'reason': context_reason}] and small['reason'] == context_reason


@pytest.mark.req('CHARACTER-EXTRACT')
def test_preview_without_memory_role_refuses(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=RoleSettings(provider=ProviderSettings(model=' ')))
    plan = extract_plan(repo, story.id)
    assert plan['ready'] is False and plan['reason'] == NO_MEMORY_ROLE and plan['plan_fingerprint'] is None
    shown = preview(repo, request(story))
    assert shown['ready'] is False and shown['reason'] == NO_MEMORY_ROLE


@pytest.mark.req('CHARACTER-EXTRACT')
def test_preview_reports_cards_protagonist_and_pending_proposal(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=local_role())
    with_cards(repo, story, 'Оля', 'Марко', marked='Оля')
    plan = extract_plan(repo, story.id)
    assert (plan['cards_count'], plan['has_protagonist']) == (2, True)
    coordinator = RunCoordinator(repo)
    run = coordinator.enqueue(request(story), 'one')
    run.state, run.checkpoint = 'completed', {'phase': 'done', 'proposal': {'fingerprint': 'f'}}
    repo.save_run(run)
    assert extract_plan(repo, story.id)['pending_proposal'] is True
    assert PENDING_PROPOSAL in preview(repo, request(story))['warnings']
    run.checkpoint = {'phase': 'done', 'proposal': {'fingerprint': 'f'}, 'accepted_at': '2026-11-25T10:00:00+00:00'}
    repo.save_run(run)
    assert extract_plan(repo, story.id)['pending_proposal'] is False
    run.checkpoint = {'phase': 'done', 'proposal': {'fingerprint': 'f'}}
    repo.save_run(run)
    newer = coordinator.enqueue(request(story), 'two')  # a newer run: the older proposal is no longer the pending one
    assert extract_plan(repo, story.id)['pending_proposal'] is False and newer.state == 'queued'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_fingerprint_changes_with_prose_cards_tariff_budget(tmp_path):
    repo, story, scenes = written_book(tmp_path, [WORDS, WORDS], memory_role=cloud_role())
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    seen = [extract_plan(repo, story.id)['plan_fingerprint']]
    assert extract_plan(repo, story.id)['plan_fingerprint'] == seen[0]  # stable while nothing changes
    save_manual_prose(repo, scenes[0].id, WORDS + ' Ще.', repo.get_scene(scenes[0].id).revision)
    seen.append(extract_plan(repo, story.id)['plan_fingerprint'])
    with_cards(repo, repo.get_story(story.id), 'Оля')
    seen.append(extract_plan(repo, story.id)['plan_fingerprint'])
    current = Tariff.model_validate(repo.billing('tariff_get', provider='openrouter', model='cloud-model',
                                                 base_url=OPENROUTER))
    save_tariff(repo, current.model_copy(update={'input_per_million': Decimal('3')}))
    seen.append(extract_plan(repo, story.id)['plan_fingerprint'])
    set_limit(repo, 'story:' + story.id, '20', 1)  # the limit row is at revision 1 after the first set
    seen.append(extract_plan(repo, story.id)['plan_fingerprint'])
    assert len(set(seen)) == len(seen)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_enqueue_stale_fingerprint_409(tmp_path):
    repo, story, scenes = written_book(tmp_path, [WORDS], memory_role=local_role())
    worker = RunCoordinator(repo)
    seen = extract_plan(repo, story.id)['plan_fingerprint']
    save_manual_prose(repo, scenes[0].id, WORDS + ' Інше.', repo.get_scene(scenes[0].id).revision)
    with pytest.raises(RevisionConflict, match=EXTRACT_PLAN_CHANGED):
        worker.enqueue(request(story, extract_plan_fingerprint=seen), 'stale')
    assert repo.list_runs(story.id) == []
    fresh = extract_plan(repo, story.id)['plan_fingerprint']
    run = worker.enqueue(request(story, group_words=5000, extract_plan_fingerprint=fresh), 'fresh')
    assert run.state == 'queued' and run.tasks == [] and run.request.scene_id is None
    assert fresh != seen and run.planned_telemetry['calls'] == 4


@pytest.mark.req('CHARACTER-EXTRACT')
def test_second_active_run_409(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=local_role())
    worker = RunCoordinator(repo)
    first = worker.enqueue(request(story), 'one')
    assert first.state == 'queued'
    with pytest.raises(RevisionConflict, match=EXTRACT_RUNNING):
        worker.enqueue(request(story), 'two')
    assert len(repo.list_runs(story.id)) == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_paused_run_does_not_block(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=local_role())
    worker = RunCoordinator(repo)
    first = worker.enqueue(request(story), 'one')
    first.state = 'paused'
    repo.save_run(first)
    assert worker.enqueue(request(story), 'two').state == 'queued'
    assert pending_preview(repo, first)['ready'] is True


@pytest.mark.req('CHARACTER-EXTRACT')
def test_allowed_in_chat_writing_mode(tmp_path):
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=local_role())
    worker = RunCoordinator(repo)
    for index, mode in enumerate(('chat', 'obscura')):
        repo.update_writing_mode(story.id, mode, repo.get_story(story.id).revision)
        assert preview(repo, request(story))['ready'] is True
        run = worker.enqueue(request(story), f'mode-{index}')
        run.state = 'cancelled'
        repo.save_run(run)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_request_validators():
    with pytest.raises(ValueError, match='лише для пошуку персонажів'):
        RunRequest(story_id='s', mode='rebuild_memory', scene_id='x', group_words=5000)
    with pytest.raises(ValueError, match='лише для пошуку персонажів'):
        RunRequest(story_id='s', mode='audit', audit_scope='story', audit_plan_fingerprint='a' * 64,
                   extract_plan_fingerprint='b' * 64)
    with pytest.raises(ValueError, match='усьому твору'):
        RunRequest(story_id='s', mode='character_extract', scene_id='x')
    with pytest.raises(ValueError):
        RunRequest(story_id='s', mode='character_extract', group_words=999)
    with pytest.raises(ValueError):
        RunRequest(story_id='s', mode='character_extract', group_words=20001)
    assert RunRequest(story_id='s', mode='character_extract', group_words=1000).group_words == 1000


def reading_run(repo, story, calls, bound, per_call_usd):
    """A paused `character_extract` run in phase `reading` with `calls` of `bound` spent, priced `per_call_usd` at start."""
    from storygen.characters.extract import ExtractState
    from storygen.domain import new_id
    from storygen.run_models import Run
    run = Run(id=new_id(), story_id=story.id, request_id='paused', state='paused', tasks=[], request=request(story),
              checkpoint={'phase': 'reading', 'state': ExtractState(calls=calls).model_dump(mode='json'), 'pending': [],
                          'calls_bound': bound, 'cost_nanos': 0, 'per_call_usd': per_call_usd})
    repo.enqueue_run(run)
    return run


@pytest.mark.req('CHARACTER-EXTRACT')
def test_resume_preview_prices_what_is_left_of_the_bound(tmp_path):
    # The resume calls what is left of the bound priced at start; a fresh plan of today (cheaper tariff, other bound)
    # must not lower the shown cost below what the run may still spend.
    repo, story, _ = written_book(tmp_path, [WORDS] * 3, memory_role=cloud_role())
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    run = reading_run(repo, story, calls=3, bound=20, per_call_usd='0.5000')
    seen = pending_preview(repo, run)
    assert seen['calls'] == 17
    assert seen['cost'] == {'per_call_usd': '0.5000', 'total_usd': '8.5000', 'reason': None}
    assert pending_preview(repo, reading_run(repo, story, calls=20, bound=20, per_call_usd='0.5000'))['cost'][
        'total_usd'] == '0.0000'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_resume_preview_without_a_start_price_keeps_the_reason(tmp_path):
    # No tariff at start (a cloud model without a stored price): no USD, and the reason of the price stays visible.
    repo, story, _ = written_book(tmp_path, [WORDS], memory_role=cloud_role())
    set_limit(repo, 'story:' + story.id, '10', 0)
    seen = pending_preview(repo, reading_run(repo, story, calls=1, bound=4, per_call_usd=None))
    assert seen['calls'] == 3 and seen['cost']['total_usd'] is None and seen['cost']['reason']
    repo, story, _ = written_book(tmp_path / 'local', [WORDS], memory_role=local_role())
    local = pending_preview(repo, reading_run(repo, story, calls=1, bound=4, per_call_usd=None))
    assert local['calls'] == 3 and local['cost'] == {'per_call_usd': None, 'total_usd': None, 'reason': None}
