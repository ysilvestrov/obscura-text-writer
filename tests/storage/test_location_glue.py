"""MEMORY-LOCATIONS-S10: glued phrases of a story (Story.location_glues) in plan saves, glue and unglue."""
import json

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.locations import location_id, normalize
from storygen.storage import locations as store
from storygen.storage.repository import Repository

PHRASE = 'бар, в якому пахне кавою'


def lid(story, *parts):
    return location_id(story.id, normalize(parts))


def story_payload(repo, story):
    with repo.db.connection() as db:
        return json.loads(db.execute('SELECT payload FROM stories WHERE id=?', (story.id,)).fetchone()[0])


def set_glues(repo, story_id, glues):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        repo._save_story(db, story.model_copy(update={'location_glues': list(glues)}))
    repo.db.bump_generation()


@pytest.mark.req('MEMORY-LOCATIONS')
def test_story_payload_without_glues_has_no_field(tmp_path):
    repo = Repository(tmp_path);story = repo.create_story(StoryCreate(title='Твір'))
    assert 'location_glues' not in story_payload(repo, story)
    set_glues(repo, story.id, [PHRASE])
    assert story_payload(repo, story)['location_glues'] == [PHRASE]
    assert repo.get_story(story.id).location_glues == [PHRASE]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_plan_save_uses_story_glues(tmp_path):
    repo = Repository(tmp_path);story = repo.create_story(StoryCreate(title='Твір'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    set_glues(repo, story.id, [PHRASE])
    saved = repo.update_scene_plan(scene.id, 'Сцена 1: Ранок\nЛокація: Бар, в якому пахне кавою, вулиця\nДії: кава.', scene.revision)
    assert saved.location_ids == [lid(story, 'Бар, в якому пахне кавою'), lid(story, 'вулиця')]


def book(tmp_path, *lines):
    """A story with one scene per «Локація:» value, plans saved in order."""
    repo = Repository(tmp_path);story = repo.create_story(StoryCreate(title='Твір'));scenes = []
    for n, line in enumerate(lines, 1):
        scene = repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}'))
        scenes.append(repo.update_scene_plan(scene.id, f'Сцена {n}: Подія\nЛокація: {line}\nДії: щось.', scene.revision))
    return repo, repo.get_story(story.id), scenes


def glue(repo, story, phrase=PHRASE):
    rev = repo.get_story(story.id).revision
    return store.change_locations(repo, story.id, rev, lambda db: store.glue_location(repo, db, story.id, phrase))


def unglue(repo, story, phrase=PHRASE):
    from storygen.locations import glue_key
    rev = repo.get_story(story.id).revision
    return store.change_locations(repo, story.id, rev, lambda db: store.unglue_location(repo, db, story.id, glue_key(phrase)))


def merged_map(repo, story):
    with repo.db.connection() as db:
        return {c.id: c.merged_into for c in store.load_locations(db, story.id).values()}


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_recomputes_plan_scenes_now(tmp_path):
    repo, story, (morning, other) = book(tmp_path, 'Бар, в якому пахне кавою, вулиця', 'Ліс')
    view = glue(repo, story)
    after = repo.get_scene(morning.id)
    assert after.location_ids == [lid(story, 'Бар, в якому пахне кавою'), lid(story, 'вулиця')]
    assert after.revision == morning.revision + 1 and after.beats == morning.beats
    assert repo.get_scene(other.id).revision == other.revision
    assert repo.get_story(story.id).location_glues == [PHRASE]
    assert view['story_revision'] == story.revision + 1
    assert view['glues'] == [{'key': 'бар, в якому пахне кавою', 'phrase': PHRASE}]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_skips_model_scenes(tmp_path):
    from tests.storage.test_story_locations import set_model_places
    repo, story, _ = book(tmp_path, 'Ліс')
    night = repo.create_scene(story.id, SceneCreate(title='Ніч', beats='Дії: тиша. Бар, в якому пахне кавою.'))
    with repo.db.connection() as db:
        ids = store.ensure_locations(db, story.id, [('Бар',), ('в якому пахне кавою',)])
    repo.db.bump_generation()
    night = set_model_places(repo, night.id, ids)
    glue(repo, story, 'бар, в якому пахне кавою')
    assert repo.get_scene(night.id).location_ids == ids and repo.get_scene(night.id).revision == night.revision


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_reaches_trashed_plan_scenes_but_not_candidates(tmp_path):
    repo, story, (kept, trashed) = book(tmp_path, 'Ліс', 'Бар, в якому пахне кавою')
    repo.set_scene_trashed(story.id, trashed.id, trashed.revision, False)
    assert store.locations_view(repo, story.id)['glue_candidates'] == []
    glue(repo, story)
    with repo.db.connection() as db:
        row = json.loads(db.execute('SELECT payload FROM scenes WHERE id=?', (trashed.id,)).fetchone()[0])
    assert row['location_ids'] == [lid(story, 'Бар, в якому пахне кавою')]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_stales_material_of_changed_scenes_only(tmp_path, monkeypatch):
    from storygen.storage import scene_metadata
    repo, story, (changed, same) = book(tmp_path, 'Бар, в якому пахне кавою', 'Ліс')
    seen = []
    real = scene_metadata.stale_scene_material
    monkeypatch.setattr(scene_metadata, 'stale_scene_material', lambda r, db, scene: (seen.append(scene.id), real(r, db, scene)))
    glue(repo, story)
    assert seen == [changed.id]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_unglue_restores_fragments(tmp_path):
    repo, story, (scene,) = book(tmp_path, 'Бар, в якому пахне кавою')
    glue(repo, story)
    view = unglue(repo, story)
    assert repo.get_scene(scene.id).location_ids == [lid(story, 'Бар'), lid(story, 'в якому пахне кавою')]
    assert view['glues'] == [] and repo.get_story(story.id).location_glues == []
    assert 'location_glues' not in story_payload(repo, story)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_unglue_after_merging_a_fragment(tmp_path):
    from storygen.locations import canonical
    repo, story, (scene,) = book(tmp_path, 'Бар, в якому пахне кавою')
    glue(repo, story)
    glued = lid(story, 'Бар, в якому пахне кавою')
    rev = repo.get_story(story.id).revision
    store.change_locations(repo, story.id, rev, lambda db: store.merge_location(db, story.id, lid(story, 'Бар'), glued))
    unglue(repo, story)
    assert lid(story, 'Бар') in repo.get_scene(scene.id).location_ids
    assert canonical(merged_map(repo, story), lid(story, 'Бар')) == glued


@pytest.mark.req('MEMORY-LOCATIONS')
@pytest.mark.parametrize('phrase,message', [
    ('Місто / бар, в якому', 'Склеїти можна лише фразу без «/»'),
    ('  ab ', 'Фраза має бути від 3 до 200 знаків'),
    ('бар ' + 'х' * 200 + ', двір', 'Фраза має бути від 3 до 200 знаків'),
    ('в якому пахне кавою', 'Фраза не охоплює жодного розрізу'),
])
def test_glue_validation(tmp_path, phrase, message):
    repo, story, (scene,) = book(tmp_path, 'Бар, в якому пахне кавою')
    before = story_payload(repo, story)
    with pytest.raises(ValueError, match=message):
        glue(repo, story, phrase)
    assert story_payload(repo, story) == before and repo.get_scene(scene.id).revision == scene.revision


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_refuses_a_repeat_the_501st_and_an_unknown_unglue(tmp_path):
    repo, story, _ = book(tmp_path, "Комора з п'ятьма, полицями")
    glue(repo, story, 'комора з п’ятьма,  полицями')
    with pytest.raises(ValueError, match='Цю назву вже склеєно'):
        glue(repo, story, "КОМОРА з п'ятьма, полицями")
    set_glues(repo, story.id, [f'місце {n}, двір' for n in range(500)])
    with pytest.raises(ValueError, match='Склеєних назв може бути не більше 500'):
        glue(repo, story, 'інше місце, сад')
    with pytest.raises(ValueError, match='Невідома склеєна назва'):
        unglue(repo, story, 'нема такої, назви')


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_dismisses_new_cards_against_fragments_with_prefixes(tmp_path):
    repo, story, _ = book(tmp_path, 'Місто / бар, в якому пахне кавою / тераса')
    glue(repo, story)
    fragments = {lid(story, 'Місто', 'бар'), lid(story, 'в якому пахне кавою'), lid(story, 'в якому пахне кавою', 'тераса')}
    new = {lid(story, 'Місто', 'бар, в якому пахне кавою'), lid(story, 'Місто', 'бар, в якому пахне кавою', 'тераса')}
    with repo.db.connection() as db:
        pairs = [set(p) for p in store.suggestions(db, story.id)]
    assert not [pair for pair in pairs if pair & new and pair & fragments]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_candidates_join_every_occurrence(tmp_path):
    repo, story, scenes = book(tmp_path, 'Місто / бар, зал', 'Село / бар, зал')
    view = store.locations_view(repo, story.id)
    [candidate] = [c for c in view['glue_candidates'] if c['key'] == 'бар, зал']
    assert candidate['phrase'] == 'бар, зал'
    assert set(candidate['card_ids']) == {lid(story, 'Місто', 'бар'), lid(story, 'Село', 'бар'), lid(story, 'зал')}
    assert candidate['scene_ids'] == [s.id for s in scenes]
    view = glue(repo, story, 'бар, зал')
    assert not [c for c in view['glue_candidates'] if c['key'] == 'бар, зал']
    assert view['glues'][0]['key'] == 'бар, зал'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_recompute_500_scenes_within_a_second(tmp_path):
    import time
    repo, story, (first,) = book(tmp_path, 'Бар, в якому пахне кавою, вулиця')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        template = json.loads(db.execute('SELECT payload FROM scenes WHERE id=?', (first.id,)).fetchone()[0])
        for n in range(500):
            row = {**template, 'id': f'bulk{n:04d}', 'position': n + 2}
            db.execute('INSERT INTO scenes VALUES(?,?,?,?)', (row['id'], story.id, row['position'], json.dumps(row, ensure_ascii=False)))
    repo.db.bump_generation()
    started = time.perf_counter()
    glue(repo, story)
    elapsed = time.perf_counter() - started
    assert repo.get_scene('bulk0499').location_ids[0] == lid(story, 'Бар, в якому пахне кавою')
    assert elapsed < 1.0, elapsed
