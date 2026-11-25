"""R-48 PR 2 (design §5.1, amendment 1): the cast of a scene without a participants line in its plan comes from the
names of the character cards mentioned in its prose, in order of first mention; no model is called."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import RevisionConflict, SceneCreate, StoryCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.repository import Repository
from storygen.storage.scene_cast import NO_CARDS_WARNING, apply_cast, cast_preview, propose_cast, view_cards


def entry(id, text):
    return {'id': id, 'text': text, 'availability': 'timeless', 'available_from_scene_id': None, 'origin': 'author',
            'sources': []}


def card(id, name, *texts):
    return {'schema_version': 2, 'id': id, 'name': name,
            'entries': [entry(f'{id}{i}', text) for i, text in enumerate(texts or ('Вік: 30',))]}


def publish_cards(repo, story_id, cards):
    ref = repo.save_version(story_id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story_id, 'characters_version_id', ref.id, repo.get_story(story_id).revision)


def book(repo, texts, cards=None, beats=None):
    story = repo.create_story(StoryCreate(title='Імпортована книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i + 1}', beats=(beats or {}).get(i, '')))
              for i in range(len(texts))]
    for scene, text in zip(scenes, texts):
        if text:
            save_manual_prose(repo, scene.id, text, repo.get_scene(scene.id).revision)
    if cards is not None:
        publish_cards(repo, story.id, cards)
    return repo.get_story(story.id), [repo.get_scene(s.id) for s in scenes]


def proposal(repo, story):
    view = repo.context_view(story.id)
    return propose_cast(view, view_cards(view))


def give_memory(repo, story, scene):
    scene = repo.get_scene(scene.id)
    memory = repo.save_version(story.id, scene.id, 'memory', '{}', [scene.heads['prose']])
    repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    return memory


def stored_stale(repo, id):
    # A memory head's shown mark comes from its link (VALID-LINKS); the invalidation writes the stored flag.
    from storygen.domain import VersionRef
    with repo.db.connection() as db:
        return repo._get(db, 'versions', id, VersionRef).stale


def test_cast_from_name_mentions_in_order(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля побачила Марка біля воріт.', 'Порожня вулиця.', ''],
                         [card('marko', 'Марко'), card('olia', 'Оля')])
    # «Марка» is found through the stem of «Марко»; order is the order of first mention, not the card order.
    assert proposal(repo, story) == {scenes[0].id: ['olia', 'marko'], scenes[1].id: []}


def test_other_name_available_in_scene_counts(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Бос мовчав. Потім прийшла Оля.'],
                         [card('olia', 'Оля'), card('boss', 'Хазяїн', 'Інше ім\'я: Бос')])
    assert proposal(repo, story) == {scenes[0].id: ['boss', 'olia']}


def test_scene_with_plan_participants_untouched(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля побачила Марка.', 'Оля сама.'], [card('marko', 'Марко'), card('olia', 'Оля')],
                         beats={0: 'Персонажі: Марко\nЗустріч.'})
    assert repo.get_scene(scenes[0].id).character_ids == ['marko']
    assert proposal(repo, story) == {scenes[1].id: ['olia']}
    assert apply_cast(repo, story.id, proposal(repo, story), repo.get_story(story.id).revision) == [scenes[1].id]
    assert repo.get_scene(scenes[0].id).character_ids == ['marko']
    # A forged proposal for a scene with a participants line is ignored inside the transaction.
    revision = repo.get_story(story.id).revision
    assert apply_cast(repo, story.id, {scenes[0].id: ['olia']}, revision) == []
    assert repo.get_scene(scenes[0].id).character_ids == ['marko']


def test_no_cards_gives_warning_and_empty_cast(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля побачила Марка.'])
    view = repo.context_view(story.id)
    assert propose_cast(view, []) == {scenes[0].id: []}
    entry_, effective = cast_preview(view)
    assert entry_ == {'cards': 0, 'protagonist': None, 'scenes_to_fill': 0, 'warning': NO_CARDS_WARNING}
    assert NO_CARDS_WARNING == 'Немає карток персонажів: пам\'ять не матиме стану героя'


def test_no_cards_warning_is_translated():
    from storygen.web.localization import diagnostic
    assert diagnostic(NO_CARDS_WARNING, 'uk') == NO_CARDS_WARNING
    assert diagnostic(NO_CARDS_WARNING, 'en') == 'No character cards: the memory will have no hero state'


def test_protagonist_marked_card_reported(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля побачила Марка.', 'Марко пішов.'],
                         [card('olia', 'Оля'), card('marko', 'Марко', 'Протагоніст')])
    entry_, _ = cast_preview(repo.context_view(story.id))
    assert entry_ == {'cards': 2, 'protagonist': 'Марко', 'scenes_to_fill': 2, 'warning': None}


def test_protagonist_defaults_to_first_of_proposed_cast(tmp_path):
    # A freshly imported book has no cast yet: the preview names the hero the build will see after the cast is applied.
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля побачила Марка.'], [card('marko', 'Марко'), card('olia', 'Оля')])
    entry_, _ = cast_preview(repo.context_view(story.id))
    assert entry_['protagonist'] == 'Оля'


def test_apply_cast_stales_existing_memory(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля йде.', 'Оля бачить Марка.'], [card('marko', 'Марко'), card('olia', 'Оля')])
    apply_cast(repo, story.id, proposal(repo, story), repo.get_story(story.id).revision)
    memory = give_memory(repo, story, scenes[1])
    assert not stored_stale(repo, memory.id)
    publish_cards(repo, story.id, [card('marko', 'Марко'), card('olia', 'Оля'), card('bob', 'Боб')])
    save_manual_prose(repo, scenes[1].id, 'Оля бачить Марка і Боба.', repo.get_scene(scenes[1].id).revision)
    # The new prose already stales the memory; restore a fresh memory over it so only the cast change is measured.
    memory = give_memory(repo, story, scenes[1])
    before = repo.get_scene(scenes[1].id)
    changed = apply_cast(repo, story.id, proposal(repo, story), repo.get_story(story.id).revision)
    after = repo.get_scene(scenes[1].id)
    assert changed == [scenes[1].id]
    assert after.character_ids == ['olia', 'marko', 'bob'] and after.revision == before.revision + 1
    assert stored_stale(repo, memory.id)


def test_apply_cast_noop_when_unchanged(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля йде.'], [card('olia', 'Оля')])
    apply_cast(repo, story.id, proposal(repo, story), repo.get_story(story.id).revision)
    memory = give_memory(repo, story, scenes[0])
    story = repo.get_story(story.id)
    scene = repo.get_scene(scenes[0].id)
    versions = len(repo.list_versions(story.id))
    assert apply_cast(repo, story.id, proposal(repo, story), story.revision) == []
    assert repo.get_story(story.id).revision == story.revision
    assert repo.get_scene(scene.id) == scene
    assert len(repo.list_versions(story.id)) == versions and not stored_stale(repo, memory.id)


def test_apply_cast_rejects_stale_revision(tmp_path):
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Оля йде.'], [card('olia', 'Оля')])
    with pytest.raises(RevisionConflict):
        apply_cast(repo, story.id, proposal(repo, story), story.revision - 1)
    assert repo.get_scene(scenes[0].id).character_ids == []


def test_apply_cast_replaces_a_cast_set_on_the_scene_card(tmp_path):
    # Design §5.1, read literally: only a participants line in the plan protects the cast; a cast set on the scene card
    # of a scene without that line is replaced by the names mentioned in its prose.
    repo = Repository(tmp_path)
    story, scenes = book(repo, ['Порожня вулиця.'], [card('olia', 'Оля')])
    repo.update_scene_metadata(scenes[0].id, {'character_ids': ['olia']}, repo.get_scene(scenes[0].id).revision)
    assert proposal(repo, story) == {scenes[0].id: []}
    assert apply_cast(repo, story.id, proposal(repo, story), repo.get_story(story.id).revision) == [scenes[0].id]
    assert repo.get_scene(scenes[0].id).character_ids == []


def test_infer_route_applies_and_returns_changed(tmp_path):
    from storygen.web.app import create_app
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story, scenes = book(repo, ['Оля побачила Марка.', 'Тиша.'], [card('marko', 'Марко'), card('olia', 'Оля')])
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    url = f'/api/stories/{story.id}/scene-cast/infer'
    response = client.post(url, json={'expected_revision': story.revision})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['changed_scene_ids'] == [scenes[0].id]
    assert data['story']['revision'] == story.revision + 1 == repo.get_story(story.id).revision
    assert repo.get_scene(scenes[0].id).character_ids == ['olia', 'marko']
    again = client.post(url, json={'expected_revision': data['story']['revision']})
    assert again.status_code == 200 and again.json()['changed_scene_ids'] == []
    assert client.post(url, json={'expected_revision': story.revision}).status_code == 409
