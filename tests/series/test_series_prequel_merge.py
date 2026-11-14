"""SERIES-S08: the start memory of a book after a prequel merges the main book and the prequels (neutral examples)."""
import json

from storygen.book.series import series_status, start_memory
from storygen.characters.models import load_characters
from storygen.memory.journal import _add_event, _change_event, replay_memory
from storygen.memory.series_start import read_series_start
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository
from tests.series.helpers import book, card, finished_book, into_series, memory, prose, publish_cards


def enter(repo, story, item, number, start=None):
    start = SeriesStart(offset=start[0], anchor=start[1]) if start else None
    return store.set_story_series(repo, story.id, item.id, number, start, repo.get_story(story.id).revision)


def snapshot(repo, story):
    story = repo.get_story(story.id)
    return read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id)


def write_prequel(repo, item, number, start, cloth, *, fact='Біля порту маяк', clothes='Сорочка', finished=True, extra=None, cards=None):
    """`cards(repo, story)` changes the prequel's cards before its memory (a later change makes the memory stale). A prequel whose only scene changes Anna's clothing and adds a fact, over its own start snapshot; `extra(base, p_id)`
    gives (sentence, events) appended to the scene."""
    story, scene = book(repo, f'Приквел {number}', written=False, cast=['A'])
    story = enter(repo, story, item, number, start)
    if story.series_start_version_id:  # the whole start memory is the prequel's past (SERIES-S09)
        store.save_decisions(repo, story.id, {f['key']: 'past' for f in store.start_facts(repo, story.id)}, story.revision)
    if cards:
        cards(repo, repo.get_story(story.id))
    if finished:
        base = snapshot(repo, story).journal
        sentence, more = extra(base, None) if extra else ('', None)
        p = prose(repo, scene, f'Анна в одязі: {clothes}. {fact}. {sentence}')
        events = [_change_event('update', cloth.claim_id, clothes, 'character_states', ['A'], p.id, f'Анна в одязі: {clothes}.',
                                slot='clothing'),
                  _add_event('facts', fact, p.id, f'{fact}.', 0)]
        if extra:
            events += extra(base, p.id)[1]
        memory(repo, scene, base, events)
    return repo.get_story(story.id)


def series_with_prequel(tmp_path, *, finished=True, extra=None, cards=None):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, cloth = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    prequel = write_prequel(repo, item, 2, ('Рік -10', 1), cloth, finished=finished, extra=extra, cards=cards)
    third, _ = book(repo, 'Книга 3', cast=['A'])
    return repo, item, first, prequel, third, cloth


def active_texts(journal):
    return sorted(e.text for e in replay_memory(journal).values())


def test_book_after_prequel_merges_main_book_and_prequel(tmp_path):
    repo, item, first, prequel, third, cloth = series_with_prequel(tmp_path)
    third = enter(repo, third, item, 3, ('Рік 2', 1))
    data = snapshot(repo, third)
    assert active_texts(data.journal) == ['Біля порту маяк', 'Сусід пішов', 'Халат']
    assert [s['story_id'] for s in data.source['sources']] == [first.id, prequel.id]
    assert data.source['resolved'] == [{'key': 'slot:A:clothing', 'kept_story_id': first.id,
                                        'dropped': [{'story_id': prequel.id, 'text': 'Сорочка'}]}]
    assert check_integrity(repo.root).ok


def test_prequel_without_summary_blocks_the_snapshot(tmp_path):
    repo, item, first, prequel, third, cloth = series_with_prequel(tmp_path, finished=False)
    third = enter(repo, third, item, 3, ('Рік 2', 1))
    assert start_memory(repo, third).missing.id == prequel.id
    assert third.series_start_version_id is None
    status = series_status(repo, third)
    assert (status.state, status.source_story_id) == ('no_summary', prequel.id)


def test_prequel_of_a_prequel_conflict_takes_the_later_prequel(tmp_path):
    # Prequel 2 (year -10) puts Anna at the port; prequel 3 (year -20) moves her to the hill. Only the prequels touch her
    # location, so the later one in the chronology (prequel 2) wins; the clothing conflict still goes to the main book.
    def at_port(base, p_id):
        return 'Анна біля порту.', ([_add_event('character_states', 'Порт', p_id, 'Анна біля порту.', 0, ['A'],
                                                slot='location')] if p_id else None)

    def on_hill(base, p_id):
        claim = next(e.claim_id for e in base.events if e.slot == 'location')
        return 'Анна на пагорбі.', ([_change_event('update', claim, 'Пагорб', 'character_states', ['A'], p_id,
                                                   'Анна на пагорбі.', slot='location')] if p_id else None)
    repo, item, first, prequel, fourth, cloth = series_with_prequel(tmp_path, extra=at_port)
    earlier = write_prequel(repo, item, 3, ('Рік -20', 1), cloth, fact='На пагорбі вежа', clothes='Плащ', extra=on_hill)
    fourth = enter(repo, fourth, item, 4, ('Рік 2', 1))
    data = snapshot(repo, fourth)
    assert [s['story_id'] for s in data.source['sources']] == [first.id, prequel.id, earlier.id]
    assert active_texts(data.journal) == ['Біля порту маяк', 'На пагорбі вежа', 'Порт', 'Сусід пішов', 'Халат']
    kept = {item['key']: item['kept_story_id'] for item in data.source['resolved']}
    assert kept == {'slot:A:clothing': first.id, 'slot:A:location': prequel.id}
    memory_of = start_memory(repo, repo.get_story(earlier.id))
    assert [s['story_id'] for s in memory_of.sources] == [first.id, prequel.id]


def test_series_4a_snapshot_reads_as_one_source(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second, _ = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    raw = json.loads(repo.read_text(second.series_start_version_id))
    main = raw.pop('sources')[0]
    raw.pop('resolved')
    raw.update({'source_story_id': first.id, 'source_summary_version_id': main['summary_version_id'],
                'source_summary_sha256': main['summary_sha256'], 'source_characters_version_id': main['characters_version_id'],
                'source_characters_sha256': main['characters_sha256'], 'source_card_hashes': main['card_hashes']})
    data = read_series_start(json.dumps(raw, ensure_ascii=False), 'v')
    assert data.source['sources'] == [main] and data.source['resolved'] == []


def test_sequential_series_snapshot_is_unchanged(tmp_path):
    from storygen.book.series import summary_journal
    from storygen.memory.series_start import inherit_journal
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, scenes, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second, _ = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    view = repo.context_view(first.id)
    text, inherited = inherit_journal(*summary_journal(view, scenes[1].heads['memory']))
    raw = json.loads(repo.read_text(second.series_start_version_id))
    assert raw['text'] == text and raw['journal'] == json.loads(inherited.model_dump_json())
    assert raw['resolved'] == []


def test_cards_come_from_main_book_then_prequels(tmp_path):
    def own_cards(repo, story):
        own = [json.loads(c.model_dump_json()) for c in load_characters(repo.read_text(story.characters_version_id))]
        own[0]['entries'] = []
        publish_cards(repo, story, own + [card('B', 'Борис')])
    repo, item, first, prequel, third, cloth = series_with_prequel(tmp_path, cards=own_cards)
    third = enter(repo, third, item, 3, ('Рік 2', 1))
    cards = {c.id: c for c in load_characters(repo.read_text(repo.get_story(third.id).characters_version_id))}
    assert sorted(cards) == ['A', 'B']
    assert [e.text for e in cards['A'].entries] == ['Лікарка']


def test_new_prequel_between_source_and_book_changes_the_status(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, cloth = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    third, _ = book(repo, 'Книга 3', cast=['A'])
    third = enter(repo, third, item, 3, ('Рік 2', 1))
    assert series_status(repo, third).state == 'fresh'
    prequel = write_prequel(repo, item, 2, ('Рік -10', 1), cloth)
    assert series_status(repo, repo.get_story(third.id)).state == 'source_changed'
    third, _ = store.refresh_snapshot(repo, third.id, repo.get_story(third.id).revision)
    status = series_status(repo, third)
    assert (status.state, [r['kept_story_id'] for r in status.resolved]) == ('fresh', [first.id])
    assert [s['story_id'] for s in snapshot(repo, third).source['sources']] == [first.id, prequel.id]
