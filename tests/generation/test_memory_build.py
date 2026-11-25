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
    """A memory head whose link holds (an author verdict): valid by freshness as well as by the stored flag."""
    from tests.link_helpers import approve_links
    scene = repo.get_scene(scene.id)
    memory = repo.save_version(story.id, scene.id, 'memory', '{}', [scene.heads['prose']])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id, [scene.id])


def rebuild(story, scene, **extra):
    return RunRequest(story_id=story.id, scene_id=scene.id, mode='rebuild_memory', **extra)


def tokens(role, chars):
    return min(role.max_input_chars, chars + role.max_input_chars // 8) * 4 + 256


def test_target_is_first_scene_without_memory(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.', 'Четверта.'])
    give_memory(repo, story, scenes[0])
    give_memory(repo, story, scenes[1])
    assert memory_build_target(repo.context_view(story.id)) == (scenes[2].id, 2)


def test_target_is_first_scene_without_memory_even_without_prose(tmp_path):
    # Design §5: the build starts at the first scene without memory; the preview then says what that scene still needs.
    repo, story, scenes = written_book(tmp_path, ['', 'Друга.', 'Третя.'])
    assert memory_build_target(repo.context_view(story.id)) == (scenes[0].id, 3)
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is False and result['reason'] == 'Спершу виберіть завершену прозу сцени 1'
    assert result['cost'] is None and result['plan_fingerprint'] is None


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


def paragraphs(chars):
    """Cyrillic prose of about `chars` characters in paragraphs of about 500."""
    words = ('Слово ' * (chars // 6 + 1))[:chars]
    return '\n\n'.join(words[i:i + 500].strip() for i in range(0, len(words), 500))


def real_request(tmp_path, prose, role):
    """The memory stage's own request for a first scene with this prose: (bundle, None) or (None, ContextOverflow)."""
    from storygen.generation.context import ContextOverflow, build_context
    repo, story, (scene,) = written_book(tmp_path, [prose], memory_role=role)
    try:
        return build_context(repo, scene.id, 'memory', role), None
    except ContextOverflow as overflow:
        return None, overflow


def passes_with_reserve(repo, bundle, role):
    """The checks `_finish_context` applies, on the stage's request plus the previous-memory reserve."""
    from storygen.providers.requests import generation_request
    from storygen.token_budget.service import token_estimate
    user = bundle.user_text + '\n\n' + 'а' * (role.max_input_chars // 8)
    if len(bundle.system_text) + len(user) > role.max_input_chars:
        return False
    request = generation_request('memory', role, bundle.system_text, user, bundle.fragments)
    return token_estimate(repo, role.provider.provider, role.provider.base_url, request)['input_tokens'] <= \
        role.context_tokens - role.max_output_tokens


def test_prose_memory_request_is_the_stage_request(tmp_path):
    from storygen.generation.memory_build import PROSE_ID_PLACEHOLDER, prose_memory_request
    role = RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072)
    prose = paragraphs(1200)
    bundle, _ = real_request(tmp_path, prose, role)
    prose_id = bundle.input_refs[0]
    system, user, fragments = prose_memory_request(role, prose)
    assert system == bundle.system_text
    assert user == bundle.user_text.replace(prose_id, PROSE_ID_PLACEHOLDER)
    assert fragments == {key: value.replace(prose_id, PROSE_ID_PLACEHOLDER) for key, value in bundle.fragments.items()}


@pytest.mark.parametrize('role', [
    RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072),
    RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072, max_input_chars=8000)],
    ids=['context-131k', 'input-8000'])
def test_memory_fits_matches_the_stage_check_on_both_sides_of_the_boundary(tmp_path, role):
    from storygen.application.manuscript_import import memory_fits
    repo = Repository(tmp_path / 'measure')
    fits = memory_fits(repo, role)
    low, high = 1, role.max_input_chars  # fits(low) and not fits(high)
    assert fits(paragraphs(low)) and not fits(paragraphs(high))
    while high - low > 50:
        middle = (low + high) // 2
        low, high = (middle, high) if fits(paragraphs(middle)) else (low, middle)
    # The largest fitting scene passes the stage's own check with the reserve to spare; the next does not.
    bundle, overflow = real_request(tmp_path / 'low', paragraphs(low), role)
    assert overflow is None and passes_with_reserve(repo, bundle, role)
    big = role.model_copy(update={'max_input_chars': 10 ** 7, 'context_tokens': 2 ** 22})
    bundle, _ = real_request(tmp_path / 'high', paragraphs(high), big)
    assert not passes_with_reserve(repo, bundle, role)
    # A scene the stage refuses outright is unfit.
    over = paragraphs(high + role.max_input_chars // 8 + 2000)
    assert real_request(tmp_path / 'over', over, role)[1] is not None and not fits(over)


def test_unfit_scenes_listed_for_small_role(tmp_path):
    role = RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072, max_input_chars=8000)
    repo, story, scenes = written_book(tmp_path, ['Коротка.', paragraphs(6000), 'Ще коротка.'], memory_role=role)
    view = repo.context_view(story.id)
    assert unfit_scenes(repo, view, role, [s.id for s in scenes]) == [scenes[1].id]
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['unfit_scenes'] == [scenes[1].id]
    assert result['ready'] is True, result['reason']  # listed in advance; the run stops on that scene itself


def test_chapter_sized_scene_fits_the_wide_role(tmp_path):
    # A 40 000-character chapter: the stage request carries the prose once, so a 131k-token, 80 000-character role holds it.
    role = RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072)
    repo, story, scenes = written_book(tmp_path, [paragraphs(40000)], memory_role=role)
    assert unfit_scenes(repo, repo.context_view(story.id), role, [scenes[0].id]) == []


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


def test_role_limits_change_the_fingerprint_and_the_worker_rejects_the_old_one(tmp_path):
    wide = RoleSettings(provider=ProviderSettings(model='memory'), context_tokens=131072)
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'], memory_role=wide)
    worker = RunCoordinator(repo)
    seen = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    assert seen is not None
    save_role_settings(repo, story.id, 'memory', wide.model_copy(update={'max_output_tokens': 4096}),
                       repo.get_story(story.id).revision)
    assert preview(repo, rebuild(story, scenes[0]))['plan_fingerprint'] != seen
    with pytest.raises(RevisionConflict, match='План побудови пам’яті змінився'):
        worker.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=seen), 'limits')
    assert worker.list_runs() == []


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

    def counting(repo, role=None, **kwargs):
        fits = original(repo, role, **kwargs)
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


def with_cards(repo, story, *names, marked=None):
    import json
    cards = [{'schema_version': 2, 'id': f'c{i}', 'name': name,
              'entries': [{'id': f'c{i}e', 'text': 'Протагоніст' if name == marked else 'Вік: 30',
                           'availability': 'timeless', 'available_from_scene_id': None, 'origin': 'author',
                           'sources': []}]} for i, name in enumerate(names)]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    return repo.get_story(story.id)


def test_readiness_reports_the_proposed_cast(tmp_path):
    from storygen.storage.scene_cast import NO_CARDS_WARNING
    repo, story, scenes = written_book(tmp_path, ['Оля побачила Марка.', 'Тиша.'])
    assert preview(repo, rebuild(story, scenes[0]))['cast'] == \
        {'cards': 0, 'protagonist': None, 'scenes_to_fill': 0, 'warning': NO_CARDS_WARNING}
    story = with_cards(repo, story, 'Марко', 'Оля')
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is True, result['reason']
    assert result['cast'] == {'cards': 2, 'protagonist': 'Оля', 'scenes_to_fill': 1, 'warning': None}


def test_no_cards_warning_does_not_block_the_run(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.'])
    result = preview(repo, rebuild(story, scenes[0]))
    assert result['ready'] is True and result['reason'] is None and result['cast']['warning']


def test_memory_fingerprint_changes_with_cards(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Оля побачила Марка.', 'Боб чекав.'])
    story = with_cards(repo, story, 'Марко', 'Оля')
    worker = RunCoordinator(repo)
    seen = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    story = with_cards(repo, story, 'Марко', 'Оля', 'Боб')  # a card mentioned in the prose: the proposed cast changes
    assert preview(repo, rebuild(story, scenes[0]))['plan_fingerprint'] != seen
    with pytest.raises(RevisionConflict, match='План побудови пам’яті змінився'):
        worker.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=seen), 'cards')
    assert worker.list_runs() == []


def valid_first_memory(repo, story, scene):
    """A memory of the first scene that a later scene's memory stage accepts as its previous memory."""
    from storygen.memory.journal import MemoryJournal
    from tests.link_helpers import approve_links
    prose = [repo.get_scene(scene.id).heads['prose']]
    memory = repo.save_version(story.id, scene.id, 'memory',
                               MemoryJournal(schema_version=3, source_prose_ids=prose).model_dump_json(), prose)
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)


@pytest.mark.parametrize('earlier_memory', [False, True])
def test_fingerprint_survives_applying_the_cast(tmp_path, earlier_memory):
    # The UI and MCP apply the proposed cast right before the run: the fingerprint the author saw must still match.
    from storygen.storage.scene_cast import apply_cast, propose_cast, view_cards
    repo, story, scenes = written_book(tmp_path, ['Оля йде.', 'Оля побачила Марка.', 'Марко пішов.'])
    if earlier_memory:  # a valid memory of the first scene: the cast change must stale it, not break the run
        valid_first_memory(repo, story, scenes[0])
    story = with_cards(repo, story, 'Марко', 'Оля')
    # The first scene's cast changes under the proposal: its memory is not valid, so the build starts there either way.
    assert memory_build_target(repo.context_view(story.id)) == (scenes[0].id, 3)
    target = scenes[0]
    seen = preview(repo, rebuild(story, target))
    assert seen['ready'] is True, seen['reason']
    view = repo.context_view(story.id)
    changed = apply_cast(repo, story.id, propose_cast(view, view_cards(view)), repo.get_story(story.id).revision)
    assert changed == [scene.id for scene in scenes]
    story = repo.get_story(story.id)
    assert memory_build_target(repo.context_view(story.id)) == (scenes[0].id, 3)
    again = preview(repo, rebuild(story, target))
    assert again['ready'] is True, again['reason']
    assert again['plan_fingerprint'] == seen['plan_fingerprint']
    assert again['cast']['scenes_to_fill'] == 0
    run = RunCoordinator(repo).enqueue(rebuild(story, target, memory_plan_fingerprint=seen['plan_fingerprint']), 'go')
    assert [task['stage'] for task in run.tasks] == ['memory'] * 3


def test_target_moves_back_to_an_earlier_scene_whose_cast_changes(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Тиша.', 'Оля йде.', 'Марко пішов.'])
    story = with_cards(repo, story, 'Марко', 'Оля')
    valid_first_memory(repo, story, scenes[0])
    give_memory(repo, story, scenes[1])
    # Scene 2 has fresh memory, but «Оля» gives it a cast it lacks: the build starts there, not at scene 3 (the first
    # without memory); scene 1 mentions nobody, so its memory stays valid.
    assert memory_build_target(repo.context_view(story.id)) == (scenes[1].id, 2)
    result = preview(repo, rebuild(story, scenes[1]))
    assert result['ready'] is True, result['reason']
    assert result['calls'] == 2 and result['cost']['calls'] == 2


def test_stale_memory_head_is_the_target(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    for scene in scenes:
        give_memory(repo, story, scene)
    assert memory_build_target(repo.context_view(story.id)) == (None, 0)
    save_manual_prose(repo, scenes[1].id, 'Інша друга.', repo.get_scene(scenes[1].id).revision)
    memory = repo.get_scene(scenes[1].id).heads['memory']
    assert repo.context_view(story.id).peek_version(memory).stale  # the head stays, its stored flag is set
    assert memory_build_target(repo.context_view(story.id)) == (scenes[1].id, 2)


def published_memory(repo, story, scenes, upto):
    """Memory of scenes[upto] through the app's own memory path: a version with a dependency snapshot."""
    from storygen.memory.journal import MemoryJournal
    from storygen.memory.service import publish_memory_journal
    from tests.link_helpers import approve_links
    prose = [repo.get_scene(s.id).heads['prose'] for s in scenes[:upto + 1]]
    scene = repo.get_scene(scenes[upto].id)
    version, _ = publish_memory_journal(repo, scene.id, MemoryJournal(schema_version=3, source_prose_ids=prose),
                                        scene.revision)
    approve_links(repo, story.id)
    return version


def test_snapshot_memory_of_a_newly_cast_scene_stays_the_target(tmp_path):
    # Review I-1: the stage's memory carries a dependency snapshot, so apply_cast leaves its stored flag alone; the cast
    # recorded in the snapshot differs from the written one, and the build still starts at that scene.
    from storygen.storage.scene_cast import apply_cast, propose_cast, view_cards
    repo, story, scenes = written_book(tmp_path, ['Тиша.', 'Оля йде.', 'Марко пішов.'])
    story = with_cards(repo, story, 'Марко', 'Оля')
    published_memory(repo, story, scenes, 0)
    memory = published_memory(repo, story, scenes, 1)
    assert repo.get_version(memory.id).dependency_snapshot is not None
    assert memory_build_target(repo.context_view(story.id)) == (scenes[1].id, 2)
    view = repo.context_view(story.id)
    changed = apply_cast(repo, story.id, propose_cast(view, view_cards(view)), repo.get_story(story.id).revision)
    assert scenes[1].id in changed
    view = repo.context_view(story.id)
    assert not view.peek_version(memory.id).stale  # the snapshot path: the stored flag is untouched
    assert memory_build_target(view) == (scenes[1].id, 2)
    # The run is never started: a later preview still starts at that scene.
    assert memory_build_target(repo.context_view(story.id)) == (scenes[1].id, 2)


def test_second_memory_build_is_refused_while_one_is_active(tmp_path):
    # Review I-1: a retried confirm (MCP) or a second tab must not queue the paid build twice; the replay of the same
    # request_id still answers the existing run, and a finished or cancelled build lets a new one start.
    from storygen.generation.memory_build import MEMORY_BUILD_RUNNING
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    coordinator = RunCoordinator(repo)
    fingerprint = preview(repo, rebuild(story, scenes[0]))['plan_fingerprint']
    first = coordinator.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=fingerprint), 'one')
    assert first.state == 'queued'
    with pytest.raises(RevisionConflict, match='Побудова пам’яті цього твору вже в черзі'):
        coordinator.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=fingerprint), 'two')
    assert coordinator.enqueue(rebuild(story, scenes[0], memory_plan_fingerprint=fingerprint), 'one').id == first.id
    assert [run.id for run in coordinator.list_runs(story.id)] == [first.id]
    for state in ('running', 'paused', 'pause_requested', 'cancellation_requested'):
        first.state = state
        repo.save_run(first)
        with pytest.raises(RevisionConflict, match=MEMORY_BUILD_RUNNING):
            coordinator.enqueue(rebuild(story, scenes[0]), 'three-' + state)
    first.state = 'cancelled'
    repo.save_run(first)
    assert coordinator.enqueue(rebuild(story, scenes[0]), 'four').state == 'queued'


def test_memory_build_running_is_translated():
    from storygen.generation.memory_build import MEMORY_BUILD_RUNNING
    from storygen.web.localization import diagnostic
    assert diagnostic(MEMORY_BUILD_RUNNING, 'en') == ('A memory build of this story is already queued, running or paused: '
                                                       'resume or cancel it in the runs panel')


def test_memory_stale_only_by_freshness_is_the_target(tmp_path):
    # Review M-3: the stored flag is not set, but the memory head's link does not hold (VALID-LINKS: unchecked here), so
    # the shown mark is stale and the build starts at that scene; once its link holds, the memory is valid again.
    from tests.link_helpers import approve_links
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    for scene in scenes:
        scene = repo.get_scene(scene.id)
        memory = repo.save_version(story.id, scene.id, 'memory', '{}', [scene.heads['prose']])
        repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    view = repo.context_view(story.id)
    head = view.peek_scene(scenes[0].id).heads['memory']
    assert not view.peek_version(head).stale and view.is_stale(head)
    assert memory_build_target(view) == (scenes[0].id, 2)
    approve_links(repo, story.id)
    assert memory_build_target(repo.context_view(story.id)) == (None, 0)


def test_memory_the_build_writes_is_valid(tmp_path):
    # Review M-3, no loop: memory written through the app's memory path, scene after scene and with no link verdicts,
    # is valid by construction — the target moves past it and ends at (None, 0).
    from storygen.memory.journal import MemoryJournal
    from storygen.memory.service import publish_memory_journal
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    for index, scene in enumerate(scenes):
        assert memory_build_target(repo.context_view(story.id)) == (scene.id, len(scenes) - index)
        prose = [repo.get_scene(s.id).heads['prose'] for s in scenes[:index + 1]]
        current = repo.get_scene(scene.id)
        publish_memory_journal(repo, scene.id, MemoryJournal(schema_version=3, source_prose_ids=prose), current.revision)
    view = repo.context_view(story.id)
    assert not any(view.is_stale(view.peek_scene(s.id).heads['memory']) for s in scenes)
    assert memory_build_target(view) == (None, 0)
