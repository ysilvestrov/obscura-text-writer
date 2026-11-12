"""MEMORY-SUMMARY-S02/S03/S04 in the request: a usable summary replaces an old block only when memory is selected."""
from dataclasses import replace

from storygen.generation.context import SUMMARY_PROJECTION, build_context
from storygen.memory.summaries import block_state, usable_summaries
from storygen.memory.summary_blocks import summary_blocks
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.snapshots import compare_snapshot
from storygen.storage.timeline_summaries import publish_summary, save_summary_version
from tests.memory.summary_helpers import long_story

SUMMARY = 'Анна приїхала до міста й оселилася біля річки.'


def settings(**values):
    return RoleSettings(provider=ProviderSettings(model='test'), **{'context_tokens': 262144, **values})


def entry(n):
    return f'Подія сцени {n}: ' + 'Анна довго йшла містом і думала про минуле. ' * 3


def story(tmp_path, publish=True, text=SUMMARY, block_change=None):
    repo, current = long_story(tmp_path, 25, memory_until=22, timeline_text=entry)
    scenes = repo.list_scenes(current.id)
    block = summary_blocks(current, scenes)[0]
    if block_change:
        block = block_change(block)
    memory_ids = [s.heads['memory'] for s in scenes[:10]]
    ref = save_summary_version(repo, current.id, block, memory_ids, text, 'model', 'uk')
    if publish:
        publish_summary(repo, current.id, block.key, ref.id, repo.get_story(current.id).revision)
    return repo, repo.get_story(current.id), repo.list_scenes(current.id), ref


def overflowing(repo, scene, cut=300):
    full = build_context(repo, scene.id, 'brief', settings())
    return build_context(repo, scene.id, 'brief', settings(max_input_chars=len(full.system_text) + len(full.user_text) - cut))


def test_fitting_request_is_byte_identical_with_a_head(tmp_path):
    repo, current, scenes, ref = story(tmp_path, publish=False)
    before = build_context(repo, scenes[22].id, 'brief', settings())
    publish_summary(repo, current.id, 'range:1-10', ref.id, current.revision)
    after = build_context(repo, scenes[22].id, 'brief', settings())
    assert after.user_text == before.user_text and after.fingerprint == before.fingerprint
    assert ref.id not in after.input_refs and after.memory_metrics['projection_version'] == 'memory-uk-v3'


def test_overflowing_request_of_scene_23_uses_the_summary(tmp_path):
    repo, current, scenes, ref = story(tmp_path)
    context = overflowing(repo, scenes[22])
    assert 'Підсумок сцен 1–10: ' + SUMMARY in context.user_text
    assert 'Подія сцени 5:' not in context.user_text and 'Подія сцени 3:' not in context.user_text
    assert ref.id in context.input_refs
    assert context.memory_metrics['projection_version'] == SUMMARY_PROJECTION
    assert context.memory_metrics['selection']['summaries'] == [{'block_key': 'range:1-10', 'version_id': ref.id}]
    selector = [s for s in context.dependency_snapshot.selectors if s.field == 'timeline_summary_heads']
    assert len(selector) == 1 and selector[0].expected == {'range:1-10': ref.id}
    assert compare_snapshot(repo.context_view(current.id), context.dependency_snapshot) == []
    block = summary_blocks(current, scenes)[0]
    newer = save_summary_version(repo, current.id, block, [s.heads['memory'] for s in scenes[:10]], 'Інший підсумок.', 'model', 'uk')
    publish_summary(repo, current.id, block.key, newer.id, repo.get_story(current.id).revision)
    changes = compare_snapshot(repo.context_view(current.id), context.dependency_snapshot)
    assert any(change.selector.field == 'timeline_summary_heads' for change in changes)


def test_scene_21_does_not_use_the_summary(tmp_path):
    repo, current, scenes, ref = story(tmp_path)
    context = overflowing(repo, scenes[20])
    assert 'Підсумок сцен' not in context.user_text and ref.id not in context.input_refs
    assert not any(s.field == 'timeline_summary_heads' for s in context.dependency_snapshot.selectors)


def test_changed_block_is_not_used_and_warns(tmp_path):
    reorder = lambda block: replace(block, scene_ids=tuple(reversed(block.scene_ids)))
    repo, current, scenes, ref = story(tmp_path, block_change=reorder)
    assert block_state(repo.context_view(current.id), current, scenes, summary_blocks(current, scenes)[0])[:2] == ('stale', 'blocks_changed')
    context = overflowing(repo, scenes[22], cut=2000)
    assert 'Підсумок сцен' not in context.user_text and ref.id not in context.input_refs
    assert 'Підсумок сцен 1–10 застарів: перебудуйте його в панелі пам’яті.' in context.context_warnings


def test_state_reasons_for_prose_and_memory_changes(tmp_path):
    repo, current, scenes, ref = story(tmp_path)
    view = repo.context_view(current.id)
    block = summary_blocks(current, scenes)[0]
    assert block_state(view, current, scenes, block)[:2] == ('fresh', None)
    assert usable_summaries(view, current, scenes, 23, 'uk')[0][0].version_id == ref.id
    moved = [s.model_copy(update={'heads': {**s.heads, 'memory': 'another'}}) if s.id == block.scene_ids[-1] else s for s in scenes]
    assert block_state(view, current, moved, block)[:2] == ('stale', 'memory_changed')
    from storygen.generation.dependencies import save_manual_prose
    save_manual_prose(repo, scenes[4].id, 'Нова проза п’ятої сцени.', repo.get_scene(scenes[4].id).revision)
    view = repo.context_view(current.id)
    fresh_scenes = repo.list_scenes(current.id)
    assert block_state(view, repo.get_story(current.id), fresh_scenes, block)[:2] == ('stale', 'stale')
