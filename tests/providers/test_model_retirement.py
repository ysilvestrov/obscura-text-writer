"""MODEL-RETIREMENT: the provider's own retirement notice in the catalog, never a guess from names."""
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from storygen.providers.catalog import model_option
from storygen.providers.discovery import discover_models
from storygen.providers.models import ModelRetirement, ProviderSettings
from storygen.providers.retirement import retirement_from, retirement_warning
from storygen.providers.venice import VeniceModelUnavailable, validate_model


def venice_row(id='gemma-test', deprecation=None):
    spec = {'uncensored': True, 'offline': False, 'availableContextTokens': 256000, 'capabilities': {'supportsResponseSchema': True}}
    if deprecation is not None:
        spec['deprecation'] = deprecation
    return {'id': id, 'object': 'model', 'owned_by': 'venice.ai', 'model_spec': spec}


@pytest.mark.req('MODEL-RETIREMENT')
def test_venice_notice_gives_the_removal_date_and_the_replacement():
    row = venice_row(deprecation={'autoRemap': True, 'date': '2026-11-30T00:00:00.000Z',
        'removesAt': '2026-12-01T00:00:00.000Z', 'replacementModelId': 'glm-test'})
    assert retirement_from('venice', row) == ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')
    assert model_option('venice', row).retirement == ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')


@pytest.mark.req('MODEL-RETIREMENT')
def test_venice_notice_without_removes_at_uses_its_date_and_may_have_no_replacement():
    row = venice_row(deprecation={'date': '2026-12-01T00:00:00.000Z'})
    assert retirement_from('venice', row) == ModelRetirement(date=date(2026, 12, 1), replacement=None)


@pytest.mark.req('MODEL-RETIREMENT')
def test_openrouter_expiration_date_has_no_replacement():
    row = {'id': 'vendor/model', 'name': 'Model', 'context_length': 1000, 'expiration_date': '2026-12-11'}
    assert retirement_from('openrouter', row) == ModelRetirement(date=date(2026, 12, 11), replacement=None)
    assert model_option('openrouter', row).retirement.replacement is None


@pytest.mark.req('MODEL-RETIREMENT')
@pytest.mark.parametrize('row', [
    venice_row(),
    venice_row(deprecation={}),
    venice_row(deprecation='soon'),
    venice_row(deprecation={'removesAt': 'not a date', 'replacementModelId': 'x'}),
    venice_row(deprecation={'removesAt': 20261201}),
])
def test_missing_or_broken_venice_notice_is_unknown_not_invented(row):
    assert retirement_from('venice', row) is None


@pytest.mark.req('MODEL-RETIREMENT')
def test_a_broken_replacement_drops_only_the_replacement():
    row = venice_row(deprecation={'removesAt': '2026-12-01', 'replacementModelId': 42})
    assert retirement_from('venice', row) == ModelRetirement(date=date(2026, 12, 1), replacement=None)


@pytest.mark.req('MODEL-RETIREMENT')
@pytest.mark.parametrize('value', [None, '', 'never', 12, '2026-13-40'])
def test_missing_or_broken_openrouter_date_is_unknown(value):
    assert retirement_from('openrouter', {'id': 'vendor/model', 'expiration_date': value}) is None
    assert retirement_from('openrouter', {'id': 'vendor/model'}) is None


@pytest.mark.req('MODEL-RETIREMENT')
def test_local_models_have_no_retirement():
    assert retirement_from('local', {'id': 'm', 'expiration_date': '2026-12-01'}) is None


@pytest.mark.req('MODEL-RETIREMENT')
def test_discovery_returns_the_notice_with_the_catalog(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    rows = [venice_row('gemma-test', {'removesAt': '2026-12-01T00:00:00.000Z', 'replacementModelId': 'glm-test'}), venice_row('glm-test')]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'data': rows}))) as client:
        found = {m.id: m for m in discover_models(ProviderSettings(provider='venice', model='discovery'), client)}
    assert found['gemma-test'].retirement == ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')
    assert found['glm-test'].retirement is None
    assert found['gemma-test'].model_dump(mode='json')['retirement'] == {'date': '2026-12-01', 'replacement': 'glm-test'}


@pytest.mark.req('MODEL-RETIREMENT')
def test_warning_names_the_model_the_date_and_the_replacement():
    assert retirement_warning('gemma-test', ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')) == (
        'Провайдер прибирає модель «gemma-test» 01.12.2026; заміна: «glm-test». Змініть модель у налаштуваннях ролі.')
    assert retirement_warning('vendor/model', ModelRetirement(date=date(2026, 12, 11), replacement=None)) == (
        'Провайдер прибирає модель «vendor/model» 11.12.2026. Змініть модель у налаштуваннях ролі.')


def catalog(*rows):
    return SimpleNamespace(models=SimpleNamespace(list=lambda extra_query=None: [SimpleNamespace(id=r['id'], model_spec=r['model_spec']) for r in rows]))


@pytest.mark.req('MODEL-RETIREMENT')
def test_a_model_missing_from_the_venice_catalog_says_it_may_have_been_removed():
    with pytest.raises(VeniceModelUnavailable) as error:
        validate_model(catalog(venice_row('glm-test')), 'gemma-test', False, require_uncensored=False)
    assert str(error.value) == 'Venice: моделі «gemma-test» немає в каталозі — провайдер міг її прибрати. Виберіть іншу модель у налаштуваннях ролі.'


@pytest.mark.req('MODEL-RETIREMENT')
def test_a_censored_model_keeps_its_own_message():
    row = venice_row('censored'); row['model_spec']['uncensored'] = False
    with pytest.raises(VeniceModelUnavailable) as error:
        validate_model(catalog(row), 'censored', False)
    assert str(error.value) == 'Venice: модель «censored» не має uncensored=true.'


@pytest.mark.req('MODEL-RETIREMENT')
def test_a_retiring_model_still_passes_the_catalog_check():
    spec = validate_model(catalog(venice_row('gemma-test', {'removesAt': '2020-01-01T00:00:00.000Z'})), 'gemma-test', False)
    assert spec['deprecation']['removesAt'].startswith('2020')


def _stream(text='Готово.'):
    import json as _json
    chunks = [{'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'm', 'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': None}]},
              {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'm', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
              {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'm', 'choices': [], 'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}}]
    return httpx.Response(200, headers={'content-type': 'text/event-stream'},
        content=''.join('data: ' + _json.dumps(c, ensure_ascii=False) + '\n\n' for c in chunks) + 'data: [DONE]\n\n')


def _bundle(provider, model):
    from storygen.generation.context import ContextBundle
    from storygen.providers.models import RoleSettings
    settings = RoleSettings(provider=ProviderSettings(provider=provider, model=model, include_usage=True))
    return ContextBundle(story_id='s', scene_id='c', stage='draft', scene_revision=0, story_revision=0, settings=settings,
        system_text='Промпт', user_text='Текст.', input_refs=[], fingerprint='f', estimated_tokens=10)


@pytest.mark.req('MODEL-RETIREMENT')
@pytest.mark.parametrize('provider,model,catalog_rows,expected', [
    ('venice', 'gemma-test', [venice_row('gemma-test', {'removesAt': '2026-12-01T00:00:00.000Z', 'replacementModelId': 'glm-test'})],
     ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')),
    ('venice', 'glm-test', [venice_row('glm-test')], None),
    ('openrouter', 'vendor/model', [{'id': 'vendor/model', 'object': 'model', 'created': 0, 'owned_by': 'x', 'context_length': 100000, 'expiration_date': '2026-12-11'}],
     ModelRetirement(date=date(2026, 12, 11), replacement=None)),
    ('openrouter', 'vendor/model', [{'id': 'vendor/model', 'object': 'model', 'created': 0, 'owned_by': 'x', 'context_length': 100000, 'expiration_date': None}], None),
])
def test_the_gateway_remembers_the_retirement_of_the_model_it_called(monkeypatch, accounted_call, provider, model, catalog_rows, expected):
    import threading
    from storygen.providers.streaming import build_generation_gateway
    monkeypatch.setenv('VENICE_API_KEY', 'test'); monkeypatch.setenv('OPENROUTER_API_KEY', 'test')
    def handler(request):
        return httpx.Response(200, json={'data': catalog_rows}) if request.method == 'GET' else _stream()
    ctx = _bundle(provider, model)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        gateway = build_generation_gateway(ctx.settings.provider, client, accounted_call(provider, model))
        events = list(gateway.stream(ctx, threading.Event()))
    assert events[-1].type == 'terminal'
    assert gateway.retirement == expected


@pytest.mark.req('MODEL-RETIREMENT')
def test_server_texts_match_the_interface_catalog_so_english_can_translate_them():
    import json as _json
    from pathlib import Path
    uk = _json.loads((Path(__file__).resolve().parents[2] / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))['uk']
    fill = lambda key, *values: uk[key].replace('{p0}', values[0]).replace('{p1}', values[1] if len(values) > 1 else '').replace('{p2}', values[2] if len(values) > 2 else '')
    assert retirement_warning('m', ModelRetirement(date=date(2026, 12, 1), replacement='r')) == fill('models.retiring_warning', 'm', '01.12.2026', 'r')
    assert retirement_warning('m', ModelRetirement(date=date(2026, 12, 1))) == fill('models.retiring_warning_no_replacement', 'm', '01.12.2026')
    with pytest.raises(VeniceModelUnavailable) as missing:
        validate_model(catalog(), 'm', False, require_uncensored=False)
    assert str(missing.value) == fill('models.missing_in_catalog', 'm')
    row = venice_row('m'); row['model_spec']['uncensored'] = False
    with pytest.raises(VeniceModelUnavailable) as censored:
        validate_model(catalog(row), 'm', False)
    assert str(censored.value) == fill('models.not_uncensored', 'm')


@pytest.mark.req('MODEL-RETIREMENT')
def test_role_check_collects_each_retiring_part_once(monkeypatch):
    from storygen.providers import schema_support
    from storygen.providers.models import ModelOption
    notices = {'main': ModelRetirement(date=date(2026, 12, 1), replacement='r1'),
               'variant': ModelRetirement(date=date(2026, 12, 11))}
    monkeypatch.setattr(schema_support, 'discover_models', lambda settings, http_client=None, **kw:
                        [ModelOption(id=key, retirement=value) for key, value in notices.items()] + [ModelOption(id='kept')])
    part = lambda model: SimpleNamespace(provider=ProviderSettings(provider='venice', model=model), context_tokens=8192, max_output_tokens=1024)
    role = part('main')
    role.low_rating_variant, role.classification = part('variant'), part('main')
    message, warnings = schema_support.role_check(role)
    assert message is None
    assert warnings == [retirement_warning('main', notices['main']), retirement_warning('variant', notices['variant'])]
    role.low_rating_variant, role.classification = None, part('kept')
    assert schema_support.role_check(role) == (None, [retirement_warning('main', notices['main'])])
