"""MODEL-RETIREMENT-S04: saving a role on a retiring model warns, never blocks, and stays quiet on catalog trouble."""
from datetime import date

import pytest

from storygen.providers import schema_support
from storygen.providers.models import ModelOption, ModelRetirement
from tests.web.test_model_schema_save import client, save_role, save_shared, story_id  # noqa: F401 (fixtures)

WARNING = 'Провайдер прибирає модель «m» 01.12.2026; заміна: «glm-test». Змініть модель у налаштуваннях ролі.'


def catalog(monkeypatch, retirement=None, fail=False):
    def fake(settings, http_client=None, *, repo=None):
        if fail:
            raise ValueError('catalog down')
        return [ModelOption(id='m', supports_schema=True, retirement=retirement)]
    monkeypatch.setattr(schema_support, 'discover_models', fake)


@pytest.mark.req('MODEL-RETIREMENT')
def test_saving_a_retiring_model_succeeds_with_a_warning(client, story_id, monkeypatch):
    catalog(monkeypatch, ModelRetirement(date=date(2026, 12, 1), replacement='glm-test'))
    for response in (save_role(client, story_id), save_shared(client, story_id)):
        assert response.status_code == 200, response.text
        assert response.json()['model_warnings'] == [WARNING]
        assert response.json()['revision'] >= 1


@pytest.mark.req('MODEL-RETIREMENT')
def test_saving_a_model_without_a_notice_has_no_warning_field(client, story_id, monkeypatch):
    catalog(monkeypatch)
    for response in (save_role(client, story_id), save_shared(client, story_id)):
        assert response.status_code == 200 and 'model_warnings' not in response.json()


@pytest.mark.req('MODEL-RETIREMENT')
def test_catalog_trouble_saves_without_a_warning(client, story_id, monkeypatch):
    catalog(monkeypatch, fail=True)
    for response in (save_role(client, story_id), save_shared(client, story_id)):
        assert response.status_code == 200 and 'model_warnings' not in response.json()
