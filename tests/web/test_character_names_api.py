"""CHARACTER-NAMES-S03/S06 (#215): the characters page warns about a name shared by several cards."""
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app

WARNING = 'Ім’я «Джон» мають кілька карток: Бос, Хазяїн; у плані воно не розпізнається.'
SHADOWED = 'Ім’я «Джон» є основним ім’ям картки «Джон» та іншим ім’ям карток: Хазяїн; у плані воно означає основну картку.'


def entry(text):
    return {'id': None, 'text': text, 'origin': 'author', 'sources': [], 'availability': 'timeless', 'available_from_scene_id': None}


def card(name, text):
    return {'id': None, 'name': name, 'entries': [entry(text)]}


AMBIGUOUS_CARDS = [card('Бос', "Інше ім'я: Джон"), card('Хазяїн', "Інше ім'я: Джон")]
FIXED_CARDS = [card('Бос', "Інше ім'я: Джон"), card('Хазяїн', "Інше ім'я: Шеф")]
SHADOWED_CARDS = [card('Джон', 'Сусід'), card('Хазяїн', "Інше ім'я: Джон")]


@pytest.mark.req('CHARACTER-NAMES')
def test_shared_name_is_warned_on_load_and_preview(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8760') as client:
        story = client.post('/api/stories', json={'title': 'Ферма'}).json()
        scene = client.post(f"/api/stories/{story['id']}/scenes", json={'title': 'Ворота'}).json()
        url = f"/api/stories/{story['id']}/characters"
        preview = client.post(url + '/preview', json={'cards': AMBIGUOUS_CARDS, 'scene_id': scene['id']}).json()
        assert WARNING in preview['warnings']
        saved = client.put(url, json={'expected_revision': client.get(url).json()['revision'], 'cards': AMBIGUOUS_CARDS})
        assert saved.status_code == 200, saved.text
        assert WARNING in saved.json()['warnings'] and WARNING in client.get(url).json()['warnings']
        fixed = client.put(url, json={'expected_revision': client.get(url).json()['revision'], 'cards': FIXED_CARDS})
        assert fixed.status_code == 200, fixed.text
        assert [c['entries'][0]['text'] for c in client.get(url).json()['cards']] == ["Інше ім'я: Джон", "Інше ім'я: Шеф"]
        assert WARNING not in fixed.json()['warnings']
        preview = client.post(url + '/preview', json={'cards': SHADOWED_CARDS, 'scene_id': scene['id']}).json()
        assert SHADOWED in preview['warnings'] and WARNING not in preview['warnings']
