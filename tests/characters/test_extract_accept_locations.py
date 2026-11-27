"""CHARACTER-EXTRACT-S13 (R-51, spec 2): accepting places of scenes — cards from paths, skips, one transaction."""
import pytest

from storygen.characters.extract_accept import (
    SKIP_NOT_AUTHOR_PROSE, SKIP_PLAN_PLACE, SKIP_PLACE_NOTHING_TO_ADD, SKIP_PROSE_CHANGED, SKIP_SCENE_TRASHED,
    current_proposal)
from storygen.domain import RevisionConflict
from storygen.generation.dependencies import save_manual_prose
from storygen.locations import location_id, normalize
from storygen.storage import locations as store
from tests.characters.test_extract_accept import accept, book, cast, cast_of, finished_run, item, snapshot, table_counts
from tests.generation.test_memory_build import with_cards
from tests.storage.test_story_locations import set_model_places


def lid(story, path):
    return location_id(story.id, normalize(path.split('/')))


def place(path, ref=None, new=True, suggested=True):
    return {'ref': ref or f'newloc-{path}', 'path': path, 'new': new, 'suggested': suggested}


def places(scene, *items, mode='set'):
    return {'scene_id': scene.id, 'mode': mode, 'places': list(items)}


def cards(repo, story):
    with repo.db.connection() as db:
        return store.load_locations(db, story.id)


def where(repo, scene):
    current = repo.get_scene(scene.id)
    return current.location_ids, current.location_source


@pytest.mark.req('CHARACTER-EXTRACT')
def test_accept_sets_and_adds_places(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    with repo.write_transaction() as db:
        (hut,) = store.ensure_locations(db, story.id, [('Хата',)])
    s2 = set_model_places(repo, s2.id, [hut])
    run = finished_run(repo, story, [s1, s2, s3], locations=[
        places(s1, place('Хата', hut, new=False), place('Село / Двір')),
        places(s2, place('Село / Сад'), mode='add'), places(s3, place('Ліс'))])
    revisions = {s.id: repo.get_scene(s.id).revision for s in (s1, s2, s3)}
    story_revision = repo.get_story(story.id).revision
    result = accept(repo, story, run, locations=[{'scene_id': s1.id, 'places': ['Хата', 'Село / Двір']},
                                                 {'scene_id': s2.id, 'places': ['Село / Сад']}])
    assert where(repo, s1) == ([hut, lid(story, 'Село / Двір')], 'model')
    assert where(repo, s2) == ([hut, lid(story, 'Село / Сад')], 'model')
    assert where(repo, s3) == ([], 'plan')  # not chosen
    assert result['changed_location_ids'] == [lid(story, 'Село'), lid(story, 'Село / Двір'), lid(story, 'Село / Сад')]
    assert cards(repo, story)[lid(story, 'Село / Сад')].parent_id == lid(story, 'Село')
    assert result['changed_scene_ids'] == [s1.id, s2.id] and result['skipped'] == []
    assert result['applied'] == [item('location', scene_id=s1.id), item('location', scene_id=s2.id)]
    assert {s.id: repo.get_scene(s.id).revision - revisions[s.id] for s in (s1, s2, s3)} == {s1.id: 1, s2.id: 1, s3.id: 0}
    assert repo.get_story(story.id).revision > story_revision
    assert current_proposal(repo, story.id) is None


@pytest.mark.req('CHARACTER-EXTRACT')
def test_place_skips_name_their_reason(tmp_path):
    repo, story, scenes = book(tmp_path, ['Хата.', 'Двір.', 'Сад.', 'Хата знову.'])
    s1, s2, s3, s4 = scenes
    with repo.write_transaction() as db:
        hut, hovel = store.ensure_locations(db, story.id, [('Хата',), ('Хатина',)])
        store.merge_location(db, story.id, hovel, hut)
    run = finished_run(repo, story, scenes, locations=[
        places(s1, place('Хата', hut, new=False)), places(s2, place('Двір')), places(s3, place('Сад')),
        places(s4, place('Хата', hut, new=False), place('Хатина'), mode='add')])
    # Between the run and the accept: s1 goes to the bin, s2's prose changes, s3's plan names a place, s4 gets the hut.
    repo.set_scene_trashed(story.id, s1.id, repo.get_scene(s1.id).revision, False)
    save_manual_prose(repo, s2.id, 'Двір. Нова проза.', repo.get_scene(s2.id).revision)
    repo.update_scene_plan(s3.id, 'Локація: Город', repo.get_scene(s3.id).revision)
    set_model_places(repo, s4.id, [hut])
    result = accept(repo, story, run, locations=[{'scene_id': s.id, 'places': [p['path'] for p in item_['places']]}
                                                 for s, item_ in zip(scenes, run.checkpoint['proposal']['locations'])])
    assert result['skipped'] == [
        {'item': item('location', scene_id=s1.id), 'reason': SKIP_SCENE_TRASHED},
        {'item': item('location', scene_id=s2.id), 'reason': SKIP_PROSE_CHANGED},
        {'item': item('location', scene_id=s3.id), 'reason': SKIP_PLAN_PLACE},
        {'item': item('location', scene_id=s4.id), 'reason': SKIP_PLACE_NOTHING_TO_ADD}]  # «Хатина» is merged into the hut
    assert where(repo, s3)[0] == [lid(story, 'Город')] and where(repo, s4) == ([hut], 'model')
    assert result['changed_location_ids'] == [] and result['changed_scene_ids'] == []
    assert lid(story, 'Двір') not in cards(repo, story)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_place_skipped_when_prose_head_is_not_author_text(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    edited = repo.save_version(story.id, s1.id, 'edited', 'Оля пішла.', [repo.get_scene(s1.id).heads['prose']])
    repo.set_head(s1.id, 'prose', edited.id, repo.get_scene(s1.id).revision)
    run = finished_run(repo, story, [repo.get_scene(s1.id)], locations=[places(s1, place('Хата'))])
    result = accept(repo, story, run, locations=[{'scene_id': s1.id, 'places': ['Хата']}])
    assert result['skipped'] == [{'item': item('location', scene_id=s1.id), 'reason': SKIP_NOT_AUTHOR_PROSE}]
    assert where(repo, s1) == ([], 'plan')


@pytest.mark.req('CHARACTER-EXTRACT')
def test_merged_and_repeated_paths_reuse_cards(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    with repo.write_transaction() as db:
        hut, hovel = store.ensure_locations(db, story.id, [('Хата',), ('Хатина',)])
        store.merge_location(db, story.id, hovel, hut)
    run = finished_run(repo, story, [s1, s2, s3], locations=[
        places(s1, place('Хатина'), place('Хата', hut, new=False)), places(s2, place('Двір')), places(s3, place('Двір'))])
    result = accept(repo, story, run, locations=[{'scene_id': s1.id, 'places': ['Хатина', 'Хата', 'Хатина']},
                                                 {'scene_id': s2.id, 'places': ['Двір']},
                                                 {'scene_id': s3.id, 'places': ['Двір']}])
    assert where(repo, s1)[0] == [hovel]  # the merged card's id; `canonical` leads it to the hut, which is not repeated
    assert where(repo, s2)[0] == where(repo, s3)[0] == [lid(story, 'Двір')]
    assert result['changed_location_ids'] == [lid(story, 'Двір')]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cast_and_places_of_one_scene_in_one_accept(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля')
    before = repo.get_scene(s1.id).revision
    run = finished_run(repo, story, [s1, s2, s3], casts=[cast(s1, 'c0')], locations=[places(s1, place('Двір'))])
    result = accept(repo, story, run, casts=[s1.id], locations=[{'scene_id': s1.id, 'places': ['Двір']}])
    assert cast_of(repo, s1) == ['c0'] and where(repo, s1) == ([lid(story, 'Двір')], 'model')
    assert repo.get_scene(s1.id).revision == before + 2
    assert result['changed_scene_ids'] == [s1.id]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_dry_run_of_places_writes_nothing(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], locations=[places(s1, place('Село / Двір'))])
    choice = {'locations': [{'scene_id': s1.id, 'places': ['Село / Двір']}]}
    before, counts, locations = snapshot(repo, story), table_counts(repo), cards(repo, story)
    preview = accept(repo, story, run, dry_run=True, **choice)
    assert snapshot(repo, story) == before and table_counts(repo) == counts and cards(repo, story) == locations
    assert preview['changed_location_ids'] == [lid(story, 'Село'), lid(story, 'Село / Двір')]
    assert accept(repo, story, run, **choice) == preview


@pytest.mark.req('CHARACTER-EXTRACT')
def test_places_not_offered_are_refused(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    run = finished_run(repo, story, [s1, s2, s3], locations=[places(s1, place('Двір'))])
    for choice in ([{'scene_id': s1.id, 'places': ['Сад']}], [{'scene_id': s2.id, 'places': ['Двір']}],
                   [{'scene_id': s1.id, 'places': ['Двір']}, {'scene_id': s1.id, 'places': []}]):
        with pytest.raises(ValueError) as refused:
            accept(repo, story, run, locations=choice)
        assert not isinstance(refused.value, RevisionConflict)  # 400, not 409
    assert where(repo, s1) == ([], 'plan')


@pytest.mark.req('CHARACTER-EXTRACT')
def test_old_proposal_without_locations_is_accepted(tmp_path):
    repo, story, (s1, s2, s3) = book(tmp_path)
    story = with_cards(repo, story, 'Оля')
    run = finished_run(repo, story, [s1, s2, s3], casts=[cast(s1, 'c0')])
    assert 'locations' not in run.checkpoint['proposal']
    with pytest.raises(ValueError):
        accept(repo, story, run, locations=[{'scene_id': s1.id, 'places': ['Двір']}])
    result = accept(repo, story, run, casts=[s1.id])
    assert result['changed_scene_ids'] == [s1.id] and result['changed_location_ids'] == []


@pytest.mark.req('MEMORY-LOCATIONS')
def test_extract_paths_respect_story_glues():
    """MEMORY-LOCATIONS-S10: a glued name the model echoes from the catalogue stays one place; an old checkpoint has none."""
    from storygen.characters.extract import ExtractState, _paths
    assert _paths('бар, в якому пахне кавою', {}, ['бар, в якому пахне кавою']) == [('бар, в якому пахне кавою',)]
    assert _paths('бар, в якому пахне кавою', {}) == [('бар',), ('в якому пахне кавою',)]
    assert ExtractState.model_validate({}).glued == []
