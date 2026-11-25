"""R-48 PR 2 (design §5): the memory-build preview — target scene, USD upper bound, unfit scenes, plan fingerprint and
the series-refresh hint."""
from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.billing.models import Tariff, utcnow
from storygen.billing.service import save_tariff, set_limit
from storygen.domain import RevisionConflict, SceneCreate, StoryCreate
from storygen.generation.audit_cost import NO_PRICE
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.memory_build import memory_build_target, memory_cost, unfit_scenes
from storygen.generation.readiness import preview
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.run_models import RunRequest
from storygen.storage.repository import Repository

OPENROUTER = 'https://openrouter.ai/api/v1'


def cloud_role(max_input_chars=1000, max_output_tokens=1000):
    return RoleSettings(provider=ProviderSettings(provider='openrouter', model='cloud-model'),
                        max_input_chars=max_input_chars, max_output_tokens=max_output_tokens)


def tariff(repo):
    return save_tariff(repo, Tariff(provider='openrouter', model='cloud-model', base_url=OPENROUTER,
                                    input_per_million='1', output_per_million='2', source='test tariff', kind='manual',
                                    expires_at=(utcnow() + timedelta(days=1)).isoformat()))


def written_book(tmp_path, texts, memory_role=None):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Імпортована книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i + 1}')) for i in range(len(texts))]
    for scene, text in zip(scenes, texts):
        if text:
            save_manual_prose(repo, scene.id, text, repo.get_scene(scene.id).revision)
    save_role_settings(repo, story.id, 'memory', memory_role or RoleSettings(provider=ProviderSettings(model='memory')),
                       repo.get_story(story.id).revision)
    return repo, repo.get_story(story.id), [repo.get_scene(s.id) for s in scenes]


def give_memory(repo, story, scene):
    scene = repo.get_scene(scene.id)
    memory = repo.save_version(story.id, scene.id, 'memory', '{}', [scene.heads['prose']])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)


def rebuild(story, scene, **extra):
    return RunRequest(story_id=story.id, scene_id=scene.id, mode='rebuild_memory', **extra)


def tokens(role, chars):
    return min(role.max_input_chars, chars + role.max_input_chars // 8) * 4 + 256


def test_target_is_first_scene_without_memory(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.', 'Четверта.'])
    give_memory(repo, story, scenes[0])
    give_memory(repo, story, scenes[1])
    assert memory_build_target(repo.context_view(story.id)) == (scenes[2].id, 2)


def test_target_skips_scene_without_finished_prose(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['', 'Друга.', 'Третя.'])
    assert memory_build_target(repo.context_view(story.id)) == (scenes[1].id, 2)


def test_target_none_when_all_scenes_have_memory(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    for scene in scenes:
        give_memory(repo, story, scene)
    assert memory_build_target(repo.context_view(story.id)) == (None, 0)


def test_cost_upper_bound_with_tariff(tmp_path):
    repo = Repository(tmp_path)
    tariff(repo)
    role = cloud_role()
    result = memory_cost(repo, role, [100, 2000])
    # Per scene: min(1000, chars + 125) * 4 + 256 input tokens at $1/M and 1000 output tokens at $2/M.
    per_scene = [Decimal(tokens(role, c)) / 10**6 + Decimal(2000) / 10**6 for c in (100, 2000)]
    up = lambda value: str(value.quantize(Decimal('0.0001'), rounding=ROUND_CEILING))
    assert result == {'per_call_usd': up(max(per_scene)), 'total_usd': up(sum(per_scene)), 'calls': 2, 'reason': None}
    assert result['total_usd'] == '0.0095'


def test_cost_unknown_without_tariff_does_not_block(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'], memory_role=cloud_role(80000))
    set_limit(repo, 'story:' + story.id, '10', 0)
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is True, result['reason']
    assert result['cost'] == {'per_call_usd': None, 'total_usd': None, 'calls': 2, 'reason': NO_PRICE}
    assert len(result['plan_fingerprint']) == 64


def test_cost_shown_even_when_the_budget_refuses(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'], memory_role=cloud_role(80000))
    tariff(repo)
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is False and result['reason'] == 'Спершу задайте явний ліміт бюджету в налаштуваннях'
    assert result['cost']['total_usd'] is not None and result['plan_fingerprint'] is None


def test_cost_local_provider_is_unknown(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    assert memory_cost(repo, RoleSettings(provider=ProviderSettings(model='memory')), [10, 20]) == \
        {'per_call_usd': None, 'total_usd': None, 'calls': 2, 'reason': None}
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is True, result['reason']
    assert result['cost'] == {'per_call_usd': None, 'total_usd': None, 'calls': 2, 'reason': None}


def test_unfit_scenes_listed_for_small_role(tmp_path):
    # 80 000 input characters (the default); the request carries the prose twice plus a 10 000-character reserve.
    role = RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072)
    repo, story, scenes = written_book(tmp_path, ['Коротка.', 'Д' * 40000, 'Ще коротка.'], memory_role=role)
    view = repo.context_view(story.id)
    assert unfit_scenes(repo, view, role, [s.id for s in scenes]) == [scenes[1].id]
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['unfit_scenes'] == [scenes[1].id]
    assert result['ready'] is True, result['reason']  # listed in advance; the run stops on that scene itself


def test_series_refresh_suggested_when_previous_book_has_memory(tmp_path):
    from storygen.storage import series as store
    from tests.series.helpers import book, finished_book, into_series
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, _, _ = finished_book(repo)
    into_series(repo, first, item.id, 1)
    extra = repo.create_scene(first.id, SceneCreate(title='Сцена 3', beats='Пізніше.'))
    second, scene = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    save_role_settings(repo, second.id, 'memory', RoleSettings(provider=ProviderSettings(model='memory')),
                       repo.get_story(second.id).revision)
    assert preview(repo, rebuild(second, scene))['series_refresh'] is False  # the source book is not finished yet
    repo.set_scene_trashed(first.id, extra.id, repo.get_scene(extra.id).revision, False)
    assert preview(repo, rebuild(repo.get_story(second.id), scene))['series_refresh'] is True
    assert preview(repo, rebuild(first, repo.list_scenes(first.id)[0]))['series_refresh'] is False


def test_plan_fingerprint_changes_with_prose_and_role(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    first = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    assert first == preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    save_manual_prose(repo, scenes[1].id, 'Інша друга.', repo.get_scene(scenes[1].id).revision)
    second = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    assert second != first
    save_role_settings(repo, story.id, 'memory', RoleSettings(provider=ProviderSettings(model='other')),
                       repo.get_story(story.id).revision)
    assert preview(repo, rebuild(story, scenes[0]))['plan_fingerprint'] not in {first, second}


def test_stale_memory_fingerprint_rejected_by_worker(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    worker = RunCoordinator(repo)
    seen = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    save_manual_prose(repo, scenes[1].id, 'Інша друга.', repo.get_scene(scenes[1].id).revision)
    with pytest.raises(RevisionConflict, match='План побудови пам’яті змінився'):
        worker.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=seen), 'stale')
    assert worker.list_runs() == []
    current = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    run = worker.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=current), 'fresh')
    assert [task['stage'] for task in run.tasks] == ['memory', 'memory']


def test_memory_fingerprint_only_for_rebuild_memory():
    with pytest.raises(ValueError, match='Відбиток плану пам’яті'):
        RunRequest(story_id='s', scene_id='x', mode='stage', stage='memory', memory_plan_fingerprint='a' * 64)
    with pytest.raises(ValueError):
        RunRequest(story_id='s', scene_id='x', mode='rebuild_memory', memory_plan_fingerprint='not-hex')
    assert RunRequest(story_id='s', scene_id='x', mode='rebuild_memory',
                      memory_plan_fingerprint='a' * 64).memory_plan_fingerprint == 'a' * 64


def test_unfit_scenes_measure_each_prose_once_across_requests(tmp_path, monkeypatch):
    import storygen.application.manuscript_import as manuscript_import
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    measured = []
    original = manuscript_import.memory_fits

    def counting(repo, role=None):
        fits = original(repo, role)
        return lambda text: measured.append(text) or fits(text)

    monkeypatch.setattr(manuscript_import, 'memory_fits', counting)
    monkeypatch.setattr('storygen.generation.memory_build._FITS_CACHE', {})
    preview(repo, rebuild(story, scenes[0]))
    assert len(measured) == 3
    preview(repo, rebuild(story, scenes[0]))
    assert len(measured) == 3  # a later request (a new view) reuses the answers
    save_manual_prose(repo, scenes[1].id, 'Інша друга.', repo.get_scene(scenes[1].id).revision)
    preview(repo, rebuild(story, scenes[0]))
    assert measured[3:] == ['Інша друга.']
