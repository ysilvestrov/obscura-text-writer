"""CHARACTER-EXTRACT (R-51): the current proposal and its atomic acceptance (extract_accept, Task 6; spec 4.3)."""
import json

import pytest

from storygen.characters.extract_accept import (
    PROPOSAL_SUPERSEDED, SKIP_CARD_GONE, SKIP_NAME_OTHER_CARD, SKIP_NAME_TAKEN, SKIP_NOT_AUTHOR_PROSE, SKIP_NOTHING_TO_ADD, SKIP_PLANNED,
    SKIP_PROSE_CHANGED, SKIP_PROTAGONIST_MARKED, SKIP_PROTAGONIST_NOT_ACCEPTED, SKIP_SCENE_TRASHED, AcceptRequest,
    accept_proposal, current_proposal)
from storygen.characters.extract_plan import extract_plan
from storygen.characters.projection import project_characters
from storygen.characters.service import read_character_material, save_character_material
from storygen.domain import RevisionConflict, new_id
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.extract_run import proposal_fingerprint
from storygen.run_models import Run, RunRequest
from storygen.storage.scene_cast import apply_cast
from tests.characters.test_extract_plan import local_role
from tests.generation.test_memory_build import valid_first_memory, with_cards, written_book

TEXTS = ['Оля пішла додому. Марко чекав біля воріт.', 'Оля повернулася вранці. Петро спав.', 'Петро прокинувся.']


def book(tmp_path, texts=TEXTS):
    return written_book(tmp_path, texts, memory_role=local_role())


def quote(scene, text):
    return {'version_id': scene.heads['prose'], 'scene_id': scene.id, 'quote': text}


def new_card(key, name, *quotes, other_names=()):
    return {'key': key, 'name': name, 'other_names': [{'name': n, 'suggested': s} for n, s in other_names],
            'quotes': list(quotes), 'first_scene_id': quotes[0]['scene_id']}


def cast(scene, *participants, mode='set'):
    return {'scene_id': scene.id, 'mode': mode, 'participants': list(participants)}


def finished_run(repo, story, scenes, state='completed', request_id='extract', **parts):
    """A `character_extract` run as Task 5 leaves it: phase `done`, the proposal with its fingerprint."""
    body = {'cards': [], 'name_updates': [], 'protagonist': None, 'casts': [], 'skipped_scenes': [], 'calls': 1,
            **parts,
            'source': {'scenes': {s.id: {'version_id': s.heads['prose'], 'sha256': repo.get_version(s.heads['prose']).sha256}
                                  for s in scenes},
                       'start_cards_version_id': repo.get_story(story.id).characters_version_id, 'group_words': 1000},
            'partial': state == 'cancelled', 'cost_usd': '0.0000'}
    body['fingerprint'] = proposal_fingerprint(body)
    run = Run(id=new_id(), story_id=story.id, request_id=request_id, state=state, tasks=[],
              request=RunRequest(story_id=story.id, mode='character_extract', group_words=1000),
              checkpoint={'phase': 'done', 'proposal': body})
    repo.enqueue_run(run)
    return run


def accept(repo, story, run, **choice):
    request = AcceptRequest(run_id=run.id, fingerprint=run.checkpoint['proposal']['fingerprint'], **choice)
    return accept_proposal(repo, story.id, request)


def cards(repo, story):
    return read_character_material(repo, story.id)['cards']


def by_name(repo, story):
    return {card['name']: card for card in cards(repo, story)}


def cast_of(repo, scene):
    return repo.get_scene(scene.id).character_ids


def item(kind, **key):
    return {'kind': kind, **key}


def version_files(tmp_path):
    return sorted(p.name for p in tmp_path.rglob('versions/*'))


def table_counts(repo):
    with repo.db.connection() as db:
        return {name: db.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                for name in ('versions', 'runs', 'run_events', 'dependency_edges')}


def snapshot(repo, story):
    with repo.db.connection() as db:
        return [tuple(row) for row in db.execute(
            'SELECT id,payload FROM scenes WHERE story_id=? UNION ALL SELECT id,payload FROM stories WHERE id=? '
            'UNION ALL SELECT id,payload FROM runs WHERE story_id=? UNION ALL SELECT id,payload FROM versions '
            'WHERE story_id=? ORDER BY 1', (story.id, story.id, story.id, story.id))]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_accept_selected_items_only(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'), other_names=[('Олечка', True), ('Ольга', False)]),
        new_card('new2', 'Марко', quote(s1, 'Марко чекав біля воріт')),
        new_card('new3', 'Петро', quote(s2, 'Петро спав'))],
        protagonist={'ref': 'new1', 'scores': [{'ref': 'new1', 'score': 1.2}]},
        casts=[cast(s1, 'new1', 'new2'), cast(s2, 'new1', 'new3'), cast(s3, 'new3')])
    assert current_proposal(repo, story.id)['run_id'] == run.id
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': ['Олечка']}, {'key': 'new3', 'names': []}],
                    protagonist=True, casts=[s2.id])
    found = by_name(repo, story)
    assert set(found) == {'Оля', 'Петро'}
    olya, petro = found['Оля'], found['Петро']
    assert [(e['text'], e['availability'], e['available_from_scene_id'], e['origin']) for e in olya['entries']] == [
        ('«Оля пішла додому»', 'from_scene', s1.id, 'model'),
        ("Інше ім'я: Олечка", 'timeless', None, 'model'),
        ('Головний герой', 'timeless', None, 'model')]
    assert olya['entries'][0]['sources'] == [{'version_id': s1.heads['prose'], 'quote': 'Оля пішла додому'}]
    assert olya['entries'][1]['sources'] == [] and olya['entries'][2]['sources'] == []
    assert [e['text'] for e in petro['entries']] == ['«Петро спав»']
    assert cast_of(repo, s2) == [olya['id'], petro['id']]
    assert cast_of(repo, s1) == [] and cast_of(repo, s3) == []
    assert result['skipped'] == []
    assert result['applied'] == [item('card', key='new1'), item('card', key='new3'), item('protagonist', ref='new1'),
                                 item('cast', scene_id=s2.id)]
    assert result['changed_card_ids'] == [olya['id'], petro['id']]
    assert result['changed_scene_ids'] == [s2.id] and result['stale_memory_scenes'] == []
    assert repo.get_run(run.id).checkpoint['accepted_at']
    assert current_proposal(repo, story.id) is None
    assert extract_plan(repo, story.id, 1000)['pending_proposal'] is False


@pytest.mark.req('CHARACTER-EXTRACT')
def test_quote_entries_per_scene_availability(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'), quote(s2, 'Оля повернулася вранці')),
        new_card('new2', 'Петро', quote(s3, 'Петро прокинувся'), quote(s2, 'Петро спав'))],
        casts=[cast(s1, 'new1'), cast(s2, 'new1')])
    repo.set_scene_trashed(story.id, s3.id, repo.get_scene(s3.id).revision, False)
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}, {'key': 'new2', 'names': []}],
                    casts=[s1.id, s2.id])
    found = by_name(repo, story)
    assert [(e['text'], e['available_from_scene_id']) for e in found['Оля']['entries']] == [
        ('«Оля пішла додому»', s1.id), ('«Оля повернулася вранці»', s2.id)]
    # The quote of the trashed scene is left out; the card keeps its other quote.
    assert [(e['text'], e['available_from_scene_id']) for e in found['Петро']['entries']] == [('«Петро спав»', s2.id)]
    assert result['skipped'] == [{'item': item('quote', key='new2', scene_id=s3.id), 'reason': SKIP_SCENE_TRASHED}]
    # CHARACTER-TIME: the quote of a later scene is not seen in an earlier one.
    from storygen.characters.models import load_characters
    loaded = load_characters(json.dumps(cards(repo, story), ensure_ascii=False))
    scenes = repo.list_scenes(story.id)
    assert 'Оля повернулася вранці' not in project_characters(loaded, scenes, s1.id).text
    assert 'Оля повернулася вранці' in project_characters(loaded, scenes, s2.id).text


@pytest.mark.req('CHARACTER-EXTRACT')
def test_new_card_name_taken_skipped(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Оля', quote(s1, 'Оля пішла додому')), new_card('new2', 'Марко', quote(s1, 'Марко чекав'))],
        protagonist={'ref': 'new1', 'scores': [{'ref': 'new1', 'score': 1.5}]})
    # The author makes «Ольга» (also known as «оля») after the run.
    payload = [{'name': 'Ольга', 'entries': [{'text': "Інше ім'я: оля", 'availability': 'timeless', 'origin': 'author'}]}]
    save_character_material(repo, story.id, payload, repo.get_story(story.id).revision)
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}, {'key': 'new2', 'names': []}],
                    protagonist=True)
    assert set(by_name(repo, story)) == {'Ольга', 'Марко'}
    assert result['skipped'] == [{'item': item('card', key='new1'), 'reason': SKIP_NAME_TAKEN},
                                 {'item': item('protagonist', ref='new1'), 'reason': SKIP_PROTAGONIST_NOT_ACCEPTED}]
    assert result['applied'] == [item('card', key='new2')]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_removed_existing_card_dropped_from_cast(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля', 'Марко')
    run = finished_run(repo, story, [s1, s2, s3], name_updates=[
        {'card_id': 'c1', 'names': [{'name': 'Марусь', 'suggested': True}]},
        {'card_id': 'c0', 'names': [{'name': 'Олечка', 'suggested': True}, {'name': 'Оля', 'suggested': True}]}],
        casts=[cast(s1, 'c0', 'c1'), cast(s2, 'c1')])
    # The author deletes «Марко» after the run.
    keep = [card for card in cards(repo, story) if card['id'] == 'c0']
    save_character_material(repo, story.id, keep, repo.get_story(story.id).revision)
    result = accept(repo, story, run, casts=[s1.id, s2.id], name_updates=[
        {'card_id': 'c1', 'names': ['Марусь']}, {'card_id': 'c0', 'names': ['Олечка', 'Оля']}])
    assert cast_of(repo, s1) == ['c0'] and cast_of(repo, s2) == []
    olya = by_name(repo, story)['Оля']
    # Only names the card does not have yet; the author's entry is untouched.
    assert [(e['text'], e['origin']) for e in olya['entries']] == [('Вік: 30', 'author'), ("Інше ім'я: Олечка", 'model')]
    assert result['skipped'] == [{'item': item('name_update', card_id='c1'), 'reason': SKIP_CARD_GONE},
                                 {'item': item('cast', scene_id=s2.id), 'reason': SKIP_NOTHING_TO_ADD}]
    assert result['changed_card_ids'] == ['c0'] and result['changed_scene_ids'] == [s1.id]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_rejected_new_card_dropped_from_cast(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Петро')
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Оля', quote(s1, 'Оля пішла додому')), new_card('new2', 'Марко', quote(s1, 'Марко чекав'))],
        casts=[cast(s1, 'new2', 'new1'), cast(s2, 'new2'), cast(s3, 'c0')])
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}], casts=[s1.id, s2.id, s3.id])
    olya = by_name(repo, story)['Оля']
    assert cast_of(repo, s1) == [olya['id']] and cast_of(repo, s2) == [] and cast_of(repo, s3) == ['c0']
    assert result['skipped'] == [{'item': item('cast', scene_id=s2.id), 'reason': SKIP_NOTHING_TO_ADD}]
    assert result['changed_scene_ids'] == [s1.id, s3.id]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_prose_changed_scene_cast_skipped(tmp_path):
    repo, story, scenes = book(tmp_path, TEXTS + ['Оля і Марко.', 'Оля сама.'])
    s1, s2, s3, s4, s5 = scenes
    story = with_cards(repo, story, 'Оля', 'Марко')
    run = finished_run(repo, story, scenes, cards=[new_card('new1', 'Петро', quote(s2, 'Петро спав'))],
                       casts=[cast(s1, 'c0'), cast(s2, 'new1'), cast(s3, 'new1'), cast(s4, 'c0', 'c1'), cast(s5, 'c0')])
    # Between the run and the accept: the prose of s2 changes, s1 goes to the bin, s4's plan names its participants and
    # s5's prose head becomes a model edit.
    save_manual_prose(repo, s2.id, 'Петро спав. Нова проза.', repo.get_scene(s2.id).revision)
    repo.set_scene_trashed(story.id, s1.id, repo.get_scene(s1.id).revision, False)
    repo.update_scene_plan(s4.id, 'Персонажі: Марко', repo.get_scene(s4.id).revision)
    edited = repo.save_version(story.id, s5.id, 'edited', 'Оля сама, відредаговано.', [repo.get_scene(s5.id).heads['prose']])
    repo.set_head(s5.id, 'prose', edited.id, repo.get_scene(s5.id).revision)
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}], casts=[s.id for s in scenes])
    petro = by_name(repo, story)['Петро']
    # The quote of the changed prose stays: its source is the version read by the run, which is never deleted.
    assert petro['entries'][0]['sources'] == [{'version_id': s2.heads['prose'], 'quote': 'Петро спав'}]
    assert cast_of(repo, s3) == [petro['id']]
    assert cast_of(repo, s2) == [] and cast_of(repo, s4) == ['c1'] and cast_of(repo, s5) == []
    assert result['skipped'] == [
        {'item': item('cast', scene_id=s1.id), 'reason': SKIP_SCENE_TRASHED},
        {'item': item('cast', scene_id=s2.id), 'reason': SKIP_PROSE_CHANGED},
        {'item': item('cast', scene_id=s4.id), 'reason': SKIP_PLANNED},
        {'item': item('cast', scene_id=s5.id), 'reason': SKIP_PROSE_CHANGED}]
    assert result['changed_scene_ids'] == [s3.id]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cast_skipped_when_prose_head_is_not_author_text(tmp_path):
    # The run read an `edited` head (e.g. a proposal from a scene re-pointed at the run's own version): not cast.
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля')
    edited = repo.save_version(story.id, s1.id, 'edited', 'Оля пішла.', [repo.get_scene(s1.id).heads['prose']])
    repo.set_head(s1.id, 'prose', edited.id, repo.get_scene(s1.id).revision)
    run = finished_run(repo, story, [repo.get_scene(s1.id)], casts=[cast(s1, 'c0')])
    result = accept(repo, story, run, casts=[s1.id])
    assert result['skipped'] == [{'item': item('cast', scene_id=s1.id), 'reason': SKIP_NOT_AUTHOR_PROSE}]
    assert cast_of(repo, s1) == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_add_mode_appends_missing_only(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля', 'Марко', 'Петро')
    apply_cast(repo, story.id, {s1.id: ['c1']}, repo.get_story(story.id).revision)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)],
                       casts=[cast(s1, 'c0', 'c1', 'c2', mode='add')])
    result = accept(repo, story, run, casts=[s1.id])
    assert cast_of(repo, s1) == ['c1', 'c0', 'c2']
    assert result['changed_scene_ids'] == [s1.id]
    # Storage: `add` appends only the missing, keeps the order, and an unchanged cast writes nothing.
    revision = repo.get_story(story.id).revision
    assert apply_cast(repo, story.id, {s1.id: ['c2', 'c0']}, revision, mode='add') == []
    assert apply_cast(repo, story.id, {s1.id: ['c1']}, revision, mode='set') == []
    assert repo.get_story(story.id).revision == revision


@pytest.mark.req('CHARACTER-EXTRACT')
def test_set_on_nonempty_applies_as_add(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля', 'Марко')
    run = finished_run(repo, story, [s1, s2, s3], casts=[cast(s1, 'c0', 'c1')])
    # The author sets a cast after the run: the proposal's `set` never overwrites it.
    apply_cast(repo, story.id, {s1.id: ['c1']}, repo.get_story(story.id).revision)
    result = accept(repo, story, run, casts=[s1.id])
    assert cast_of(repo, s1) == ['c1', 'c0']
    assert result['applied'] == [item('cast', scene_id=s1.id)] and result['skipped'] == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_protagonist_skipped_when_author_marked(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля')
    protagonist = {'ref': 'c0', 'scores': [{'ref': 'c0', 'score': 2.0}]}
    first = finished_run(repo, story, [s1, s2, s3], request_id='one', protagonist=protagonist)
    assert accept(repo, story, first, protagonist=True)['applied'] == [item('protagonist', ref='c0')]
    assert [e['text'] for e in by_name(repo, story)['Оля']['entries']] == ['Вік: 30', 'Головний герой']
    # A later run proposes another hero; the author already marked one (here: the accepted marker), so it is skipped.
    story = repo.get_story(story.id)
    payload = cards(repo, story) + [{'name': 'Марко', 'entries': []}]
    save_character_material(repo, story.id, payload, story.revision)
    marko = by_name(repo, story)['Марко']['id']
    second = finished_run(repo, story, [s1, s2, s3], request_id='two',
                          protagonist={'ref': marko, 'scores': [{'ref': marko, 'score': 2.0}]})
    result = accept(repo, story, second, protagonist=True)
    assert result['skipped'] == [{'item': item('protagonist', ref=marko), 'reason': SKIP_PROTAGONIST_MARKED}]
    assert by_name(repo, story)['Марко']['entries'] == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_english_story_uses_english_markers(tmp_path):
    from storygen.characters.acquaintance import is_protagonist_line
    from storygen.characters.names import card_names
    from storygen.characters.models import load_characters
    repo, story, (s1, s2, s3) = book(tmp_path, ['Olya went home.', 'Quiet.', 'Quiet.'])
    repo.update_story_language(story.id, 'en', repo.get_story(story.id).revision)
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Olya', quote(s1, 'Olya went home'), other_names=[('Olenka', True), ('Olga', True)])],
        protagonist={'ref': 'new1', 'scores': [{'ref': 'new1', 'score': 1.0}]})
    accept(repo, story, run, cards=[{'key': 'new1', 'names': ['Olenka', 'Olga']}], protagonist=True)
    card = load_characters(json.dumps(cards(repo, story), ensure_ascii=False))[0]
    assert [e.text for e in card.entries] == ['“Olya went home”', 'Other names: Olenka, Olga', 'Main character']
    assert card_names(card) == ['Olya', 'Olenka', 'Olga'] and is_protagonist_line(card.entries[2].text)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_dry_run_writes_nothing_counts_stale_memory(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    valid_first_memory(repo, story, s1)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)],
                       cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))],
                       casts=[cast(s1, 'new1'), cast(s2, 'new1')])
    choice = {'cards': [{'key': 'new1', 'names': []}], 'casts': [s1.id, s2.id]}
    before, counts, files = snapshot(repo, story), table_counts(repo), version_files(tmp_path)
    preview = accept(repo, story, run, dry_run=True, **choice)
    assert snapshot(repo, story) == before and table_counts(repo) == counts and version_files(tmp_path) == files
    assert preview['stale_memory_scenes'] == [s1.id]  # s2 has no memory
    assert preview['changed_scene_ids'] == [s1.id, s2.id] and len(preview['changed_card_ids']) == 1
    assert current_proposal(repo, story.id)['run_id'] == run.id
    result = accept(repo, story, run, **choice)
    assert {k: v for k, v in result.items() if k != 'changed_card_ids'} == \
        {k: v for k, v in preview.items() if k != 'changed_card_ids'}
    memory = repo.get_scene(s1.id).heads['memory']
    assert repo.context_view(story.id).peek_version(memory).stale  # the cast change stales the memory (stored flag)
    assert len(version_files(tmp_path)) == len(files) + 1  # one new version of the cards


@pytest.mark.req('CHARACTER-EXTRACT')
def test_second_accept_409(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    accept(repo, story, run, cards=[{'key': 'new1', 'names': []}])
    with pytest.raises(RevisionConflict):
        accept(repo, story, run, cards=[{'key': 'new1', 'names': []}])
    with pytest.raises(RevisionConflict):  # a dry run of an accepted proposal is refused too
        accept(repo, story, run, dry_run=True)
    assert set(by_name(repo, story)) == {'Оля'}


@pytest.mark.req('CHARACTER-EXTRACT')
def test_newer_run_supersedes_409(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    old = finished_run(repo, story, [s1, s2, s3], state='cancelled', request_id='old',
                       cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    assert current_proposal(repo, story.id)['run_id'] == old.id  # a cancelled run's partial proposal is current
    newer = Run(id=new_id(), story_id=story.id, request_id='newer', state='failed', tasks=[],
                request=RunRequest(story_id=story.id, mode='character_extract', group_words=1000))
    repo.enqueue_run(newer)
    assert current_proposal(repo, story.id) is None
    with pytest.raises(RevisionConflict, match=PROPOSAL_SUPERSEDED):
        accept(repo, story, old, cards=[{'key': 'new1', 'names': []}])
    assert cards(repo, story) == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_wrong_fingerprint_409(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    with pytest.raises(RevisionConflict):
        accept_proposal(repo, story.id, AcceptRequest(run_id=run.id, fingerprint='0' * 64,
                                                      cards=[{'key': 'new1', 'names': []}]))
    other = Run(id=new_id(), story_id=story.id, request_id='rebuild', state='completed', tasks=[],
                request=RunRequest(story_id=story.id, scene_id=s1.id, mode='rebuild_memory'))
    repo.enqueue_run(other)
    with pytest.raises(RevisionConflict):  # not a character_extract run
        accept_proposal(repo, story.id, AcceptRequest(run_id=other.id, fingerprint='0' * 64))
    assert cards(repo, story) == [] and not repo.get_run(run.id).checkpoint.get('accepted_at')


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unknown_items_are_refused(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'), other_names=[('Олечка', True)])])
    for choice in ({'cards': [{'key': 'new9', 'names': []}]}, {'cards': [{'key': 'new1', 'names': ['Вигадка']}]},
                   {'casts': [s1.id]}, {'name_updates': [{'card_id': 'c0', 'names': ['A']}]}, {'protagonist': True}):
        with pytest.raises(ValueError) as refused:
            accept(repo, story, run, **choice)
        assert not isinstance(refused.value, RevisionConflict)  # 400, not 409
    assert cards(repo, story) == [] and current_proposal(repo, story.id)['run_id'] == run.id


@pytest.mark.req('CHARACTER-EXTRACT')
def test_saved_cards_pass_raw_quote_check_on_next_save(tmp_path):
    # The whole path: a real run over prose with Markdown emphasis, the accept, then the author saves the cards as is.
    from tests.generation.test_audit_run import drive
    from tests.generation.test_extract_run import Script, start
    reply = json.dumps({'new_cards': [{'key': 'n1', 'name': 'Оля', 'other_names': ['Олечка'],
                                       'quotes': ['Оля пішла додому']}],
                        'scenes': [{'scene': 's1', 'participants': ['n1']}],
                        'protagonist_candidates': [{'id': 'n1', 'score': 1.0}]}, ensure_ascii=False)
    repo, story, (s1,) = book(tmp_path, ['**Оля** пішла\nдодому. ' + ' '.join(['слово'] * 600) + '.'])
    worker, run = start(repo, story, Script(reply))
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    proposal = current_proposal(repo, story.id)['proposal']
    choice = {'cards': [{'key': c['key'], 'names': [n['name'] for n in c['other_names']]} for c in proposal['cards']],
              'protagonist': True, 'casts': [c['scene_id'] for c in proposal['casts']]}
    result = accept(repo, story, run, **choice)
    assert result['skipped'] == []
    saved = read_character_material(repo, story.id)
    olya = saved['cards'][0]
    cited = olya['entries'][0]['sources'][0]['quote']
    assert '\n' in cited and '**' in cited and cited in repo.read_text(s1.heads['prose'])  # the original span
    assert cast_of(repo, s1) == [olya['id']]
    again = save_character_material(repo, story.id, saved['cards'], saved['revision'])
    assert again['cards'] == saved['cards']


def names_of(card):
    from storygen.characters.models import load_characters
    from storygen.characters.names import card_names
    return card_names(load_characters(json.dumps([card], ensure_ascii=False))[0])


@pytest.mark.req('CHARACTER-EXTRACT')
def test_name_of_another_card_is_skipped(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля', 'Марко')
    run = finished_run(repo, story, [s1, s2, s3], cards=[
        new_card('new1', 'Петро', quote(s2, 'Петро спав'), other_names=[('Марко', True), ('Петрик', True)])],
        name_updates=[
            {'card_id': 'c0', 'names': [{'name': n, 'suggested': True} for n in ('Марко', 'Петрик', 'Олечка')]},
            {'card_id': 'c1', 'names': [{'name': 'Олечка', 'suggested': True}]}])
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': ['Марко', 'Петрик']}], name_updates=[
        {'card_id': 'c0', 'names': ['Марко', 'Петрик', 'Олечка']}, {'card_id': 'c1', 'names': ['Олечка']}])
    found = by_name(repo, story)
    # The new card is still created under its free main name; a name of a current card or of a card accepted earlier in
    # the same request is never given to a second card.
    assert names_of(found['Петро']) == ['Петро', 'Петрик']
    assert names_of(found['Оля']) == ['Оля', 'Олечка']
    assert names_of(found['Марко']) == ['Марко']
    assert result['skipped'] == [
        {'item': item('name', key='new1', name='Марко'), 'reason': SKIP_NAME_OTHER_CARD},
        {'item': item('name', card_id='c0', name='Марко'), 'reason': SKIP_NAME_OTHER_CARD},
        {'item': item('name', card_id='c0', name='Петрик'), 'reason': SKIP_NAME_OTHER_CARD},
        {'item': item('name', card_id='c1', name='Олечка'), 'reason': SKIP_NAME_OTHER_CARD}]
    assert result['applied'] == [item('card', key='new1'), item('name_update', card_id='c0')]


def chained_memory(repo, story, first, second):
    """A valid memory of `second` built over the memory of `first` (the previous memory is an input of the next one)."""
    from storygen.memory.journal import MemoryJournal
    from tests.link_helpers import approve_links
    valid_first_memory(repo, story, first)
    previous = repo.get_scene(first.id).heads['memory']
    prose = repo.get_scene(second.id).heads['prose']
    memory = repo.save_version(story.id, second.id, 'memory',
                               MemoryJournal(schema_version=3, source_prose_ids=[prose]).model_dump_json(), [prose, previous])
    repo.set_head(second.id, 'memory', memory.id, repo.get_scene(second.id).revision)
    approve_links(repo, story.id)


def memory_valid(repo, story, scene):
    from storygen.generation.memory_build import _memory_valid
    view = repo.context_view(story.id)
    current = view.get_scene(scene.id)
    return _memory_valid(view, current.heads['memory'], current)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_first_cards_of_the_book_report_all_stale_memory(tmp_path):
    # A book without cards (an imported manuscript): the first version of the cards stales the memory of every scene,
    # not only of the scenes whose cast changes, and the author must see that cost before accepting.
    repo, story, (s1, s2, s3) = book(tmp_path)
    valid_first_memory(repo, story, s1)
    valid_first_memory(repo, story, s2)
    assert memory_valid(repo, story, s1) and memory_valid(repo, story, s2)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)],
                       cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    choice = {'cards': [{'key': 'new1', 'names': []}]}
    preview = accept(repo, story, run, dry_run=True, **choice)
    assert preview['changed_scene_ids'] == [] and preview['stale_memory_scenes'] == [s1.id, s2.id]
    result = accept(repo, story, run, **choice)
    assert result['stale_memory_scenes'] == [s1.id, s2.id]
    assert not memory_valid(repo, story, s1) and not memory_valid(repo, story, s2)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cast_change_reports_stale_memory_of_later_scenes(tmp_path):
    # The cast of the first scene changes; the memory of the second scene is built over the first one's memory, so the
    # invalidation stales it too.
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Марко')
    chained_memory(repo, story, s1, s2)
    assert memory_valid(repo, story, s1) and memory_valid(repo, story, s2)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)], casts=[cast(s1, 'c0')])
    preview = accept(repo, story, run, dry_run=True, casts=[s1.id])
    assert preview['changed_scene_ids'] == [s1.id] and preview['stale_memory_scenes'] == [s1.id, s2.id]
    result = accept(repo, story, run, casts=[s1.id])
    assert result['stale_memory_scenes'] == [s1.id, s2.id]
    assert not memory_valid(repo, story, s1) and not memory_valid(repo, story, s2)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_new_cards_version_alone_keeps_memory_valid(tmp_path):
    # With cards already in the book, a new version of the cards without a cast change stales no memory: the memory does
    # not depend on the cards version.
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Марко')
    chained_memory(repo, story, s1, s2)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)],
                       cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}])
    assert result['applied'] == [item('card', key='new1')] and result['stale_memory_scenes'] == []
    assert memory_valid(repo, story, s1) and memory_valid(repo, story, s2)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_new_cards_version_keeps_memory_the_stage_wrote(tmp_path):
    # The same through memory written by the real memory stage (not a hand-made version): its inputs do not include
    # the cards version, so a card-only accept on a book that already has cards stales nothing.
    from storygen.generation.context import build_context
    from tests.generation.test_memory_v4_pipeline import _run, role
    from tests.memory.wire_helpers import core_unchanged, v4_response
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Марко')
    apply_cast(repo, story.id, {s1.id: ['c0']}, repo.get_story(story.id).revision)  # a tracked character in the scene
    s1 = repo.get_scene(s1.id)
    attempt = _run(repo, s1, build_context(repo, s1.id, 'memory', role()), v4_response(core_unchanged('c0')))
    assert attempt.state == 'completed', attempt.error
    assert memory_valid(repo, story, s1)
    run = finished_run(repo, story, [repo.get_scene(s.id) for s in (s1, s2, s3)],
                       cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))])
    preview = accept(repo, story, run, dry_run=True, cards=[{'key': 'new1', 'names': []}])
    assert preview['stale_memory_scenes'] == []
    result = accept(repo, story, run, cards=[{'key': 'new1', 'names': []}])
    assert result['stale_memory_scenes'] == [] and memory_valid(repo, story, s1)
