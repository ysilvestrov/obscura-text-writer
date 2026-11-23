import json
import pytest
from storygen.storage.snapshots import freshness
from storygen.storage.links import scene_validity
from storygen.generation.dependencies import save_manual_prose
from storygen.memory.service import save_scene_memory
from tests.storage.test_links import book, save_manual_brief, memory_text

pytestmark = pytest.mark.req('VALID-LINKS')


def heads(repo, scene):
    return repo.get_scene(scene.id).heads


def stale(repo, story, version_id):
    return freshness(repo.context_view(story.id), version_id)


def test_style_edit_keeps_heads_fresh(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    ref = repo.save_version(story.id, None, 'style', 'Новий стиль', [])
    repo.publish_story_material(story.id, 'style_version_id', ref.id, repo.get_story(story.id).revision)
    for head in ('brief', 'prose', 'memory'):
        assert not stale(repo, story, heads(repo, scene)[head]).stale, head
    assert not repo.get_scene(scene.id).needs_review


def test_manual_brief_head_is_stale_with_link_reason(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, scene)
    result = stale(repo, story, heads(repo, scene)['brief'])
    assert result.stale and [r.reason for r in result.reasons] == ['link_unchecked']
    prose = stale(repo, story, heads(repo, scene)['prose'])
    assert prose.stale and [r.reason for r in prose.reasons] == ['link_unchecked']
    assert repo.get_scene(scene.id).needs_review


def test_accepted_prose_is_fresh_but_scene_unchecked(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    preview = repo.preview_prose_acceptance(story.id)
    assert [item['scene_id'] if isinstance(item, dict) else item.scene_id for item in preview['scenes']] == [scene.id]
    repo.accept_all_prose(story.id, preview['fingerprint'])
    assert not stale(repo, story, heads(repo, scene)['prose']).stale
    assert not repo.get_scene(scene.id).needs_review
    assert scene_validity(repo.context_view(story.id), scene.id) == 'unchecked'
    assert repo.preview_prose_acceptance(story.id)['scenes'] == []


def test_generated_prose_is_not_offered_for_acceptance(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    assert repo.preview_prose_acceptance(story.id)['scenes'] == []


def test_non_head_versions_keep_snapshot_comparison(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    draft = heads(repo, scene)['draft']
    assert not stale(repo, story, draft).stale
    save_manual_brief(repo, scene)
    assert stale(repo, story, draft).stale  # the draft head still compares its snapshot (head/brief changed)


def test_previous_memory_change_does_not_stale_next_memory_head(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    journal = json.loads(memory_text(repo, scenes[0]))
    journal['events'][-1]['text'] = 'Олена в бібліотеці вночі'
    save_scene_memory(repo, scenes[0].id, json.dumps(journal, ensure_ascii=False), repo.get_scene(scenes[0].id).revision)
    assert not stale(repo, story, heads(repo, scenes[1])['memory']).stale
    assert stale(repo, story, heads(repo, scenes[1])['brief']).stale  # Z1 of the next scene: previous memory changed
