import threading
from storygen.storage.snapshots import freshness
from storygen.storage.links import scene_links, scene_validity
from storygen.storage.link_records import LinkInvalidation, write_invalidation, write_verdict, new_verdict_id
from storygen.storage.link_decisions import decide_link, invalidate_links
from storygen.generation.pipeline import generate_scene
from tests.generation.test_scene_pipeline import FakeGateway
from tests.storage.test_links import book, save_manual_brief, roles, run_for
from tests.storage.test_link_records import verdict

REASON = {'kind': 'character', 'ids': ['c1']}
STAMP = '2026-11-23T00:00:00+00:00'


def statuses(repo, story, scene):
    view = repo.context_view(story.id)
    return {link: (state.status, state.source) for link, state in scene_links(view, scene.id).items()}


def fingerprint(repo, story, scene, link):
    return scene_links(repo.context_view(story.id), scene.id)[link].fingerprint


def test_invalidation_unchecks_construction_and_author_verdicts(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    generated, approved = scenes
    save_manual_brief(repo, approved)
    decide_link(repo, approved.id, 'brief', 'approve', fingerprint(repo, story, approved, 'brief'))
    decide_link(repo, approved.id, 'prose', 'approve', fingerprint(repo, story, approved, 'prose'))
    assert scene_validity(repo.context_view(story.id), approved.id) == 'valid'
    assert scene_validity(repo.context_view(story.id), generated.id) == 'valid'

    written = invalidate_links(repo, story.id, [generated.id, approved.id], REASON)
    assert sorted(written) == sorted([generated.id, approved.id])
    for scene in (generated, approved):
        current = statuses(repo, story, scene)
        assert current['brief'] == ('unchecked', None) and current['prose'] == ('unchecked', None), current
        assert current['memory'][0] == 'valid'  # Z3 is not a card link
        view = repo.context_view(story.id)
        assert scene_validity(view, scene.id) == 'unchecked'
        heads = repo.get_scene(scene.id).heads
        # The heads go stale by the 2a rule; the author's own brief stays fresh (it never blocks the draft).
        for head in (('brief', 'prose') if scene is generated else ('prose',)):
            result = freshness(view, heads[head])
            assert result.stale and [r.reason for r in result.reasons] == ['link_unchecked'], head
        assert not freshness(view, heads['memory']).stale
        assert repo.context_view(story.id).effective_scene(scene.id).needs_review

    for scene in (generated, approved):
        for link in ('brief', 'prose'):
            decide_link(repo, scene.id, link, 'approve', fingerprint(repo, story, scene, link))
        # A later valid verdict ends the invalidation: construction counts again for the generated scene.
        assert statuses(repo, story, scene)['brief'] == ('valid', 'construction' if scene is generated else 'author')
        assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


def test_invalidation_with_old_fingerprint_is_inert(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    invalidate_links(repo, story.id, [scene.id], REASON)
    assert statuses(repo, story, scene)['brief'] == ('unchecked', None)
    # The scene is generated again: new brief and prose, new fingerprints; the recorded ones no longer match.
    attempts = generate_scene(repo, scene.id, roles(), lambda _: FakeGateway(repo, scene.id), threading.Event(),
                              lambda *_: None, run_id=run_for(repo, story, scene, 'again-' + scene.id))
    assert all(a.state == 'completed' for a in attempts), [(a.stage, a.state, a.error) for a in attempts]
    assert statuses(repo, story, scene) == {link: ('valid', 'construction') for link in ('brief', 'prose', 'memory')}


def test_invalidation_for_another_fingerprint_does_not_apply(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    record = LinkInvalidation(id=new_verdict_id(), story_id=story.id, scene_id=scene.id, links=['brief'],
                              fingerprints={'brief': 'f' * 64}, reason=REASON, created_at=STAMP)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        write_invalidation(db, record)
    assert statuses(repo, story, scene)['brief'] == ('valid', 'construction')


def _write(repo, *records):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for record in records:
            (write_invalidation if isinstance(record, LinkInvalidation) else write_verdict)(db, record)


def test_approval_right_after_invalidation_wins(tmp_path):
    # Insertion order decides, not created_at: both records carry the same timestamp.
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, scene)
    state = scene_links(repo.context_view(story.id), scene.id)['brief']
    invalidation = lambda: LinkInvalidation(id=new_verdict_id(), story_id=story.id, scene_id=scene.id, links=['brief'],
                                            fingerprints={'brief': state.fingerprint}, reason=REASON, created_at=STAMP)
    approval = lambda: verdict(story.id, scene.id, fingerprint=state.fingerprint, inputs=state.inputs, created_at=STAMP)
    _write(repo, invalidation(), approval())
    assert statuses(repo, story, scene)['brief'] == ('valid', 'author')
    _write(repo, approval(), invalidation())
    assert statuses(repo, story, scene)['brief'] == ('unchecked', None)
    _write(repo, approval())
    assert statuses(repo, story, scene)['brief'] == ('valid', 'author')


def test_invalidation_keeps_a_later_discrepancy(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    state = scene_links(repo.context_view(story.id), scene.id)['brief']
    invalidate_links(repo, story.id, [scene.id], REASON)
    _write(repo, verdict(story.id, scene.id, fingerprint=state.fingerprint, inputs=state.inputs, source='auditor',
                         outcome='discrepancy', discrepancies=[{'text': 'Інше ім’я', 'quote': None}]))
    assert statuses(repo, story, scene)['brief'] == ('discrepancy', 'auditor')


def test_invalidation_skips_missing_links(tmp_path):
    from storygen.domain import SceneCreate
    repo, story, (scene,) = book(tmp_path)
    empty = repo.create_scene(story.id, SceneCreate(title='Порожня', beats='Ніч'))
    assert invalidate_links(repo, story.id, [scene.id, empty.id], REASON) == [scene.id]
    view = repo.context_view(story.id)
    assert [(r.scene_id, r.links) for r in view.link_invalidations] == [(scene.id, ['brief', 'prose'])]
