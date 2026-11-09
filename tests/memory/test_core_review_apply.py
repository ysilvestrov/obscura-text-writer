import pytest

from storygen.domain import RevisionConflict, SceneCreate
from storygen.memory.core_review import CoreReviewBody, apply_core_review, core_review
from storygen.memory.journal import load_memory, replay_memory
from storygen.memory.projection import READER_UNKNOWN, project_memory
from storygen.memory.service import save_scene_memory
from storygen.storage.snapshots import resolve_freshness
from tests.memory.test_core_review import PROSE1, PROSE2, by_slot, manual_scene, v4_scene


def body(scene, *edits, memory_version_id=None, expected_revision=None):
    return CoreReviewBody.model_validate({'expected_revision': scene.revision if expected_revision is None else expected_revision,
        'memory_version_id': memory_version_id or scene.heads['memory'], 'edits': list(edits)})


def slot_edit(slot, action, text=None, quote=None, evidence_version_id=None, character_id='A'):
    return {'kind': 'slot', 'character_id': character_id, 'slot': slot, 'action': action, 'text': text, 'quote': quote,
            'evidence_version_id': evidence_version_id}


def thread_edit(claim_id, action, text=None, quote=None, evidence_version_id=None):
    return {'kind': 'thread', 'claim_id': claim_id, 'action': action, 'text': text, 'quote': quote,
            'evidence_version_id': evidence_version_id}


def memory_versions(repo, scene):
    return [v.id for v in repo.list_versions(scene.story_id, scene.id) if v.kind == 'memory']


def head_journal(repo, scene_id):
    scene = repo.get_scene(scene_id)
    return scene, load_memory(repo.read_text(scene.heads['memory']))


def slots_of(journal):
    return {(c.character_ids[0], c.slot): c for c in replay_memory(journal).values() if c.slot}


def test_confirm_without_edits(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    before = memory_versions(repo, scene)
    review = apply_core_review(repo, scene.id, body(scene))
    assert review['memory_version_id'] == scene.heads['memory'] and review['confirmation']['by'] == 'author'
    assert repo.get_version(scene.heads['memory']).memory_confirmation is not None
    assert memory_versions(repo, scene) == before and repo.get_scene(scene.id).revision == scene.revision


@pytest.mark.req('MEMORY-CONFIRM')
def test_keep_unknown_restores_slot(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    old_head = scene.heads['memory']
    review = apply_core_review(repo, scene.id, body(scene, slot_edit('carried', 'keep')))
    fresh, journal = head_journal(repo, scene.id)
    assert fresh.heads['memory'] != old_head and review['memory_version_id'] == fresh.heads['memory']
    slots = slots_of(journal)
    assert slots[('A', 'carried')].claim_id == claims['key'].claim_id and slots[('A', 'carried')].text == 'Ключ'
    assert slots[('A', 'clothing')].text == 'Пальто'
    # No atmosphere record of the kept slot and no retire of it.
    p2 = fresh.heads['prose']
    own = [e for e in journal.events if e.source_version_id == p2]
    assert not any(e.claim_id == claims['key'].claim_id or e.resolves_claim_id == claims['key'].claim_id for e in own)
    # The rebuilt journal still closes the thread from the model answer, with its resolution fact (I3).
    assert any(e.category == 'facts' and e.resolves_claim_id == claims['thread'].claim_id for e in own)
    assert repo.get_version(fresh.heads['memory']).memory_confirmation is not None
    assert review['confirmation'] is not None and review['revision'] == fresh.revision
    assert by_slot(review)[('A', 'carried')]['after'] == 'Ключ'


@pytest.mark.req('MEMORY-CONFIRM')
def test_keep_closed_thread_stays_open(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    apply_core_review(repo, scene.id, body(scene, thread_edit(claims['thread'].claim_id, 'keep')))
    fresh, journal = head_journal(repo, scene.id)
    active = replay_memory(journal)
    assert active[claims['thread'].claim_id].text == 'Хто стукав?'
    assert not any(e.resolves_claim_id == claims['thread'].claim_id for e in journal.events)
    # Other model decisions stay as answered.
    assert slots_of(journal)[('A', 'clothing')].text == 'Пальто' and ('A', 'carried') not in slots_of(journal)


def test_set_slot_without_quote_is_reader_unknown(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    apply_core_review(repo, scene.id, body(scene, slot_edit('location', 'set', 'Кухня'), slot_edit('clothing', 'set', 'Плащ')))
    fresh, journal = head_journal(repo, scene.id)
    slots = slots_of(journal)
    location, clothing = slots[('A', 'location')], slots[('A', 'clothing')]
    assert (location.source_kind, location.quote, location.evidence_version_id, location.text) == ('author', None, None, 'Кухня')
    # A set over an occupied slot updates the same claim; the model's own change of it is replaced by the author's.
    assert clothing.claim_id == claims['cloth'].claim_id and (clothing.text, clothing.source_kind, clothing.quote) == ('Плащ', 'author', None)
    assert not any(e.text == 'Пальто' for e in journal.events)
    text = project_memory(journal, ['A'], {}, tracked=['A']).text
    assert 'місце: Кухня' + READER_UNKNOWN in text and 'одяг: Плащ' + READER_UNKNOWN in text
    assert repo.get_version(fresh.heads['memory']).memory_confirmation is not None


def test_set_slot_with_prefix_quote(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    s1 = [s for s in repo.list_scenes(story.id) if s.position == 0][0]
    p1, p2 = s1.heads['prose'], scene.heads['prose']
    apply_core_review(repo, scene.id, body(scene,
        slot_edit('body', 'set', 'Втомлена', 'Анна в халаті.', p1),
        slot_edit('location', 'set', 'Під дверима', 'Стукав сусід.'),
        slot_edit('company', 'set', 'Сусід', 'Стукав сусід.', p2)))
    fresh, journal = head_journal(repo, scene.id)
    slots = slots_of(journal)
    body_slot, location, company = slots[('A', 'body')], slots[('A', 'location')], slots[('A', 'company')]
    assert (body_slot.source_kind, body_slot.quote, body_slot.evidence_version_id, body_slot.source_version_id) == ('author', 'Анна в халаті.', p1, p2)
    assert (location.quote, location.evidence_version_id, location.source_version_id) == ('Стукав сусід.', None, p2)
    # The current scene's prose as evidence is the default source, never a separate evidence version.
    assert company.evidence_version_id is None
    assert READER_UNKNOWN not in project_memory(journal, ['A'], {}, tracked=['A']).text


def test_close_thread_by_author(tmp_path):
    repo, story, scene, claims = manual_scene(tmp_path)
    thread = claims['thread'].claim_id
    review = apply_core_review(repo, scene.id, body(scene, thread_edit(thread, 'close', 'Стукав сусід', 'Стукав сусід.')))
    fresh, journal = head_journal(repo, scene.id)
    retire = [e for e in journal.events if e.claim_id == thread and e.operation == 'retire']
    fact = [e for e in journal.events if e.resolves_claim_id == thread]
    assert [(e.text, e.source_kind, e.quote) for e in retire] == [('Стукав сусід', 'author', 'Стукав сусід.')]
    assert [(e.category, e.text, e.source_kind, e.quote) for e in fact] == [('facts', 'Стукав сусід', 'author', 'Стукав сусід.')]
    closed = [t for t in review['threads'] if t['claim_id'] == thread]
    assert closed == [{'claim_id': thread, 'text': 'Хто стукав?', 'status': 'closed', 'resolution': 'Стукав сусід'}]


def test_close_thread_without_quote(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    thread = claims['thread'].claim_id
    review = apply_core_review(repo, scene.id, body(scene, thread_edit(thread, 'close', 'Сусід позичав сіль')))
    fresh, journal = head_journal(repo, scene.id)
    retire = [e for e in journal.events if e.claim_id == thread and e.operation == 'retire']
    assert [(e.text, e.source_kind, e.quote) for e in retire] == [('Сусід позичав сіль', 'author', None)]
    # I4 exception: an unquoted author retire carries no resolution fact; the model's own closure is replaced.
    assert not any(e.resolves_claim_id == thread for e in journal.events)
    assert [t['resolution'] for t in review['threads'] if t['claim_id'] == thread] == ['Сусід позичав сіль']


def third_scene(repo, story):
    s3 = repo.create_scene(story.id, SceneCreate(title='С3', beats='Анна.', character_ids=['A']))
    p3 = repo.save_version(story.id, s3.id, 'manual', 'Анна пішла спати.', [])
    repo.set_head(s3.id, 'prose', p3.id, repo.get_scene(s3.id).revision)
    return repo.get_scene(s3.id)


def test_author_quote_must_be_in_prefix(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    s3 = third_scene(repo, story)
    before = memory_versions(repo, scene)
    wrong = [slot_edit('location', 'set', 'Кухня', 'Цього речення немає.'),
             slot_edit('location', 'set', 'Кухня', 'Анна пішла спати.', s3.heads['prose']),
             slot_edit('location', 'set', 'Кухня', 'Анна пішла спати.'),
             thread_edit(claims['thread'].claim_id, 'close', 'Сусід', 'Анна пішла спати.', s3.heads['prose'])]
    for edit in wrong:
        with pytest.raises(ValueError, match='Цитату не знайдено в прозі цієї або попередніх сцен'):
            apply_core_review(repo, scene.id, body(scene, edit))
    assert memory_versions(repo, scene) == before and repo.get_scene(scene.id).heads == scene.heads


@pytest.mark.req('MEMORY-CONFIRM')
def test_keep_rejected_without_wire(tmp_path):
    repo, story, scene, claims = manual_scene(tmp_path)
    before = memory_versions(repo, scene)
    for edit in [slot_edit('carried', 'keep'), thread_edit(claims['thread'].claim_id, 'keep')]:
        with pytest.raises(ValueError, match='Лишити попереднє недоступне: у цієї версії немає відповіді моделі'):
            apply_core_review(repo, scene.id, body(scene, edit))
    assert memory_versions(repo, scene) == before
    # Author entries still land on top of the head journal.
    apply_core_review(repo, scene.id, body(scene, slot_edit('body', 'set', 'Втомлена')))
    fresh, journal = head_journal(repo, scene.id)
    old = load_memory(repo.read_text(scene.heads['memory']))
    assert journal.events[:len(old.events)] == old.events
    assert slots_of(journal)[('A', 'body')].text == 'Втомлена' and slots_of(journal)[('A', 'location')].text == 'Кухня'


def test_post_conflict_when_head_changed(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    old_head = scene.heads['memory']
    # The author's review was based on a head that a manual save has since replaced.
    save_scene_memory(repo, scene.id, repo.read_text(old_head).replace('Пальто', 'Пальто сіре'), scene.revision)
    current = repo.get_scene(scene.id)
    before = memory_versions(repo, scene)
    for stale in [body(current, slot_edit('location', 'set', 'Кухня'), memory_version_id=old_head),
                  body(current, memory_version_id=old_head),
                  body(current, slot_edit('location', 'set', 'Кухня'), expected_revision=scene.revision)]:
        with pytest.raises(RevisionConflict):
            apply_core_review(repo, scene.id, stale)
    assert memory_versions(repo, scene) == before and repo.get_scene(scene.id).heads == current.heads
    assert all(repo.get_version(v).memory_confirmation is None for v in before)


def test_edits_make_next_scene_memory_stale(tmp_path):
    repo, story, scene, claims, attempt = v4_scene(tmp_path)
    s3 = third_scene(repo, story)
    previous = load_memory(repo.read_text(scene.heads['memory']))
    from storygen.memory.journal import _extend
    save_scene_memory(repo, s3.id, _extend(previous, s3.heads['prose'], []).model_dump_json(), s3.revision)
    m3 = repo.get_scene(s3.id).heads['memory']
    assert resolve_freshness(repo.context_view(story.id), m3).stale is False
    apply_core_review(repo, scene.id, body(scene, slot_edit('carried', 'keep')))
    assert resolve_freshness(repo.context_view(story.id), m3).stale is True


def test_manual_save_unchanged(tmp_path):
    repo, story, scene, claims = manual_scene(tmp_path)
    head = scene.heads['memory']
    ref = repo.get_version(head)
    assert ref.kind == 'memory' and ref.dependency_snapshot is not None and ref.memory_confirmation is None
    # Re-saving the same text is still a no-op that keeps the head and revision.
    assert save_scene_memory(repo, scene.id, repo.read_text(head), scene.revision).id == head
    assert repo.get_scene(scene.id).revision == scene.revision


def test_edit_body_validation():
    for bad in [slot_edit('location', 'set'), slot_edit('location', 'set', '  '), {**slot_edit('location', 'keep'), 'text': 'x'},
                slot_edit('location', 'set', 'Кухня', None, 'v1'), thread_edit('c1', 'close'), thread_edit('c1', 'set', 'x')]:
        with pytest.raises(ValueError):
            CoreReviewBody.model_validate({'expected_revision': 1, 'memory_version_id': 'm', 'edits': [bad]})
    with pytest.raises(ValueError):
        CoreReviewBody.model_validate({'expected_revision': 1, 'memory_version_id': 'm',
            'edits': [slot_edit('location', 'keep'), slot_edit('location', 'set', 'Кухня')]})
