"""PLAN-PREAMBLE-S01..S03: saving the plan preamble publishes a new plan version (neutral examples)."""
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import RevisionConflict, StoryCreate
from storygen.generation.context import build_context
from storygen.plan_sections import PreambleError, split_plan
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.plan_preamble import read_plan_preamble, replace_plan_preamble
from storygen.storage.repository import Repository
from storygen.web.app import create_app

PLAN = '# Маяк\n\nТон: тихий.\n\n## Сцена 1: Лист\nОпис листа\n## Сцена 2: Шторм\nОпис шторму\n'


def imported(tmp_path, plan=PLAN):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Маяк'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=plan.encode())])
    return repo, story


def context(repo, scene_id):
    return build_context(repo, scene_id, 'brief', RoleSettings(provider=ProviderSettings(model='fake'))).user_text


def test_read_returns_the_preamble_and_plan_version(tmp_path):
    repo, story = imported(tmp_path)
    data = read_plan_preamble(repo, story.id)
    assert data == {'text': '# Маяк\n\nТон: тихий.', 'plan_version_id': repo.active_source(story.id, 'source_plan').id,
                    'editable': True, 'reason': None}


def test_story_without_plan_or_scene_boundaries_is_not_editable(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Без плану'))
    assert read_plan_preamble(repo, story.id)['reason'] == 'no_plan'
    repo, story = imported(tmp_path / 'plain', 'Просто опис без сцен')
    assert read_plan_preamble(repo, story.id)['editable'] is False


def test_saving_publishes_a_fresh_plan_with_the_same_scenes(tmp_path):
    repo, story = imported(tmp_path)
    before = repo.active_source(story.id, 'source_plan')
    scenes = repo.list_scenes(story.id)
    result = replace_plan_preamble(repo, story.id, before.id, '# Маяк\n\nТон: похмурий.')
    after = repo.active_source(story.id, 'source_plan')
    assert result['changed'] and after.id == result['plan_version_id'] != before.id
    assert not after.stale and after.input_refs == [before.id]
    text = repo.read_text(after.id)
    assert split_plan(text)[0] == '# Маяк\n\nТон: похмурий.\n\n'
    assert [s.text for s in split_plan(text)[1]] == [s.text for s in split_plan(repo.read_text(before.id))[1]]
    assert [s.heads for s in repo.list_scenes(story.id)] == [s.heads for s in scenes]
    assert result['revision'] == repo.get_story(story.id).revision > story.revision
    ctx = context(repo, scenes[0].id)
    assert 'Тон: похмурий.' in ctx and 'Тон: тихий.' not in ctx


def test_unchanged_preamble_creates_no_version(tmp_path):
    repo, story = imported(tmp_path)
    before = repo.active_source(story.id, 'source_plan').id
    result = replace_plan_preamble(repo, story.id, before, '  # Маяк\r\n\r\nТон: тихий.\r\n')
    assert not result['changed'] and repo.active_source(story.id, 'source_plan').id == before


def test_prose_and_prepared_canon_become_stale_cards_do_not(tmp_path):
    """Owner decision 19.11.2026: canon prepared from the plan goes stale, as after an additive import."""
    from storygen.storage.snapshots import build_dependency_snapshot
    repo, story = imported(tmp_path)
    import_sources(repo, story.id, [SourceFile(name='characters.md', raw='## Анна\nДоглядачка маяка'.encode(), kind='source_characters')])
    plan = repo.active_source(story.id, 'source_plan')
    scene = repo.list_scenes(story.id)[0]
    snapshot = build_dependency_snapshot(repo.context_view(story.id), None, 'prepare', RoleSettings(provider=ProviderSettings(model='fake')), [plan.id])
    canon = repo.save_version(story.id, None, 'canon', 'Маяк на скелі.', [plan.id], dependency_snapshot=snapshot)
    story = repo.get_story(story.id)
    story.canon_version_id = canon.id
    with repo.db.connection() as db:
        repo._save_story(db, story)
    cards = story.characters_version_id
    prose = repo.save_version(story.id, scene.id, 'edited', 'Тихий ранок.', [plan.id])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    assert not repo.context_view(story.id).is_stale(canon.id)
    replace_plan_preamble(repo, story.id, plan.id, 'Тон: похмурий.')
    view = repo.context_view(story.id)
    assert repo.get_version(prose.id).stale and repo.get_scene(scene.id).needs_review
    assert view.is_stale(canon.id)
    assert cards and not view.is_stale(cards)
    with pytest.raises(ValueError, match='застарілий'):
        context(repo, scene.id)


def test_stale_plan_version_is_a_conflict_and_changes_nothing(tmp_path):
    repo, story = imported(tmp_path)
    plan = repo.active_source(story.id, 'source_plan').id
    replace_plan_preamble(repo, story.id, plan, 'Перша правка')
    current = repo.active_source(story.id, 'source_plan').id
    with pytest.raises(RevisionConflict):
        replace_plan_preamble(repo, story.id, plan, 'Друга правка')
    assert repo.active_source(story.id, 'source_plan').id == current


def test_refused_preamble_changes_nothing(tmp_path):
    repo, story = imported(tmp_path)
    plan = repo.active_source(story.id, 'source_plan').id
    revision = repo.get_story(story.id).revision
    with pytest.raises(PreambleError):
        replace_plan_preamble(repo, story.id, plan, '# Маяк\n\n## Тон\nпохмурий')
    assert repo.active_source(story.id, 'source_plan').id == plan and repo.get_story(story.id).revision == revision


def test_series_lines_are_refused_in_an_edition_with_series(tmp_path, monkeypatch):
    from storygen import build_edition
    if not build_edition.current().long_prose:
        pytest.skip('edition without series')
    repo, story = imported(tmp_path)
    plan = repo.active_source(story.id, 'source_plan').id
    with pytest.raises(ValueError, match='Серію'):
        replace_plan_preamble(repo, story.id, plan, 'Серія: Маяки\nНомер: 2')
    assert repo.active_source(story.id, 'source_plan').id == plan


def test_http_read_and_save(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=PLAN.encode())])
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        data = client.get(f'/api/stories/{story.id}/plan-preamble').json()
        assert data['text'] == '# Маяк\n\nТон: тихий.' and data['editable']
        saved = client.put(f'/api/stories/{story.id}/plan-preamble',
                           json={'text': 'Тон: похмурий.', 'expected_plan_version_id': data['plan_version_id']})
        assert saved.status_code == 200 and saved.json()['changed']
        assert 'material_status' in saved.json() and 'impact_status' not in saved.json()
        assert client.get(f'/api/stories/{story.id}/plan-preamble').json()['text'] == 'Тон: похмурий.'
        stale = client.put(f'/api/stories/{story.id}/plan-preamble',
                           json={'text': 'Інше', 'expected_plan_version_id': data['plan_version_id']})
        assert stale.status_code == 409
        refused = client.put(f'/api/stories/{story.id}/plan-preamble',
                             json={'text': '## Тон', 'expected_plan_version_id': saved.json()['plan_version_id']})
        assert refused.status_code == 400 and 'поділ' in refused.json()['detail']


def test_crlf_plan_reads_as_lf_and_unchanged_save_is_a_no_op(tmp_path):
    repo, story = imported(tmp_path, PLAN.replace('\n', '\r\n'))
    data = read_plan_preamble(repo, story.id)
    assert data['text'] == '# Маяк\n\nТон: тихий.'
    assert not replace_plan_preamble(repo, story.id, data['plan_version_id'], data['text'])['changed']


def test_settings_page_has_the_preamble_panel_in_both_languages(tmp_path):
    import json
    from pathlib import Path
    app = create_app(AppSettings(data_dir=tmp_path))
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        page = client.get(f'/stories/{story.id}/settings').text
    assert 'id="plan-preamble-form"' in page and '/static/plan-preamble.js' in page
    catalog = json.loads((Path(__file__).parents[2] / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))
    keys = {k for k in catalog['uk'] if k.startswith('plan_preamble.')}
    assert keys and keys == {k for k in catalog['en'] if k.startswith('plan_preamble.')}


def test_server_messages_are_translated_in_the_browser_catalog():
    """The browser translates a server message that equals a catalog value (i18n.js exactDiagnostics)."""
    import json
    from pathlib import Path
    catalog = json.loads((Path(__file__).parents[2] / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))['uk']
    values = set(catalog.values())
    assert {str(PreambleError('boundary')), str(PreambleError('no_scenes'))} <= values
    source = (Path(__file__).parents[2] / 'src/storygen/storage/plan_preamble.py').read_text(encoding='utf-8')
    for key in ['plan_preamble.series', 'plan_preamble.conflict', 'plan_preamble.no_plan']:
        assert catalog[key] in source
