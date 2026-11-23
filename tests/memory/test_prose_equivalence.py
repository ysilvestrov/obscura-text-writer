import pytest
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_prose
from storygen.memory.reuse import _candidate
from storygen.storage.link_decisions import decide_link
from storygen.storage.link_records import ProseEquivalence, equivalent_pairs, new_verdict_id, write_equivalence
from storygen.storage.links import link_state
from tests.storage.test_links import book, statuses, memory_text

BLOCKED = 'Спершу оновіть пам’ять попередньої сцени'


def edit_prose(repo, scene, text):
    save_manual_prose(repo, scene.id, text, repo.get_scene(scene.id).revision)
    return repo.get_scene(scene.id).heads['prose']


def keep_memory(repo, story, scene):
    state = link_state(repo.context_view(story.id), scene.id, 'memory')
    return decide_link(repo, scene.id, 'memory', 'approve', state.fingerprint)


def brief_context(repo, scene):
    return build_context(repo, scene.id, 'brief', RoleSettings(provider=ProviderSettings(model='planner')))


@pytest.mark.req('VALID-MEMORY')
def test_author_keeps_memory_after_prose_edit(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    old = repo.get_scene(scene.id).heads['prose']
    new = edit_prose(repo, scene, 'Олена увійшла до старої бібліотеки.')
    assert statuses(repo, story, scene)['memory'] == ('unchecked', None, None)
    result = keep_memory(repo, story, scene)
    assert result['link']['status'] == 'valid' and result['link']['source'] == 'author'
    assert statuses(repo, story, scene)['memory'] == ('valid', 'author', None)
    (record,) = repo.context_view(story.id).prose_equivalences
    assert (record.scene_id, record.old_prose_id, record.new_prose_id) == (scene.id, old, new)
    verdict = next(v for v in repo.context_view(story.id).link_verdicts.values() if v.link == 'memory')
    assert record.verdict_id == verdict.id


@pytest.mark.req('VALID-MEMORY')
def test_kept_memory_unblocks_the_next_scene(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    edit_prose(repo, scenes[0], 'Олена увійшла до старої бібліотеки.')
    with pytest.raises(ValueError, match=BLOCKED):
        brief_context(repo, scenes[1])
    keep_memory(repo, story, scenes[0])
    brief_context(repo, scenes[1])


@pytest.mark.req('VALID-MEMORY')
def test_memory_without_snapshot_can_be_kept(tmp_path):
    # Final review 2a, Important 3: a memory without a snapshot blocked the next scene with no author decision.
    repo, story, scenes = book(tmp_path, 2)
    current = repo.get_scene(scenes[0].id)
    legacy = repo.save_version(story.id, scenes[0].id, 'memory', memory_text(repo, scenes[0]), [current.heads['prose']])
    repo.set_head(scenes[0].id, 'memory', legacy.id, current.revision)
    assert statuses(repo, story, scenes[0])['memory'] == ('unchecked', None, None)
    with pytest.raises(ValueError, match=BLOCKED):
        brief_context(repo, scenes[1])
    keep_memory(repo, story, scenes[0])
    assert statuses(repo, story, scenes[0])['memory'] == ('valid', 'author', None)
    assert repo.context_view(story.id).prose_equivalences == []  # the journal is made from the current prose
    brief_context(repo, scenes[1])


@pytest.mark.req('VALID-MEMORY')
def test_equivalence_chain_is_transitive(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    first = repo.get_scene(scenes[0].id).heads['prose']
    edit_prose(repo, scenes[0], 'Олена увійшла до старої бібліотеки.')
    keep_memory(repo, story, scenes[0])
    third = edit_prose(repo, scenes[0], 'Олена тихо увійшла до бібліотеки вночі.')
    keep_memory(repo, story, scenes[0])
    view = repo.context_view(story.id)
    assert (first, third) in equivalent_pairs(view, scenes[0].id)
    assert _candidate(view, scenes[1].id)[3] is False


@pytest.mark.req('VALID-MEMORY')
def test_equivalent_pairs_close_a_chain_within_one_scene(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    a, b, c = (repo.get_scene(scenes[0].id).heads['prose'], edit_prose(repo, scenes[0], 'Друга.'),
               edit_prose(repo, scenes[0], 'Третя.'))
    other = repo.get_scene(scenes[1].id).heads['prose']
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for scene, old, new in ((scenes[0], a, b), (scenes[0], b, c), (scenes[1], other, other)):
            write_equivalence(db, ProseEquivalence(id=new_verdict_id(), story_id=story.id, scene_id=scene.id,
                                                   old_prose_id=old, new_prose_id=new, verdict_id='v',
                                                   created_at='2026-11-23T00:00:00+00:00'))
    view = repo.context_view(story.id)
    assert equivalent_pairs(view, scenes[0].id) == {(a, b), (b, c), (a, c)}
    assert equivalent_pairs(repo, scenes[0].id) == {(a, b), (b, c), (a, c)}  # a Repository caller (execute_stage)
