"""STORY-LANGUAGE-S02/S03: English requests carry no Ukrainian framing; a foreign scene gets one prose directive (#32)."""
import re

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from types import SimpleNamespace

from storygen.generation.context_labels import LABELS, label
from storygen.story_horizon import horizon_instructions
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.story_time import day_label
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository

CYRILLIC = re.compile('[Ѐ-ӿ]')


def role(**values):
    return RoleSettings(provider=ProviderSettings(model='test'), **{'context_tokens': 262144, **values})


def world(tmp_path, language='en', prose_language=None, cards=None):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language=language))
    if cards:
        english_cards(repo, story, cards)
    first = repo.create_scene(story.id, SceneCreate(title='Home', beats='Start: day 1, 08:00\nAnna at home.', character_ids=['A']))
    second = repo.create_scene(story.id, SceneCreate(title='Pier', beats='Start: day 2, 09:00\nAnna waits at the pier.',
                                                    character_ids=['A'], prose_language=prose_language))
    prose = repo.save_version(story.id, first.id, 'manual', 'Anna is at home in a blue robe.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    events = [_add_event('facts', 'The lighthouse stands on the old map', prose.id, 'at home', 0),
              _add_event('timeline', 'Anna found the map', prose.id, 'at home', 1)]
    journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=events)
    memory = repo.save_version(story.id, first.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    brief = repo.save_version(story.id, second.id, 'brief', '{"objective":"Anna waits","beats":["She waits"],"constraints":[],"proposed_changes":[]}', [])
    repo.set_head(second.id, 'brief', brief.id, repo.get_scene(second.id).revision)
    draft = repo.save_version(story.id, second.id, 'draft', 'Anna waited at the pier until dusk.', [brief.id])
    repo.set_head(second.id, 'draft', draft.id, repo.get_scene(second.id).revision)
    prose2 = repo.save_version(story.id, second.id, 'manual', 'Anna waited at the pier until dusk.', [draft.id])
    repo.set_head(second.id, 'prose', prose2.id, repo.get_scene(second.id).revision)
    return repo, story, repo.get_scene(second.id), draft


def texts(context):
    return context.system_text + '\n' + context.user_text


@pytest.mark.req('STORY-LANGUAGE')
def test_label_tables_have_same_keys():
    for key, values in LABELS.items():
        assert set(values) == {'uk', 'en'}, key
        assert not CYRILLIC.search(values['en']), key


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('stage', ['brief', 'draft', 'edit', 'memory'])
def test_english_request_has_no_cyrillic(tmp_path, stage):
    repo, story, scene, draft = world(tmp_path)
    context = build_context(repo, scene.id, stage, role())
    found = CYRILLIC.findall(texts(context))
    assert not found, ''.join(found)[:80]


@pytest.mark.req('STORY-LANGUAGE')
def test_english_rewrite_request_has_no_cyrillic(tmp_path):
    repo, story, scene, draft = world(tmp_path)
    context = build_context(repo, scene.id, 'rewrite', role(), editor_source_id=draft.id)
    assert not CYRILLIC.search(texts(context))


@pytest.mark.req('STORY-LANGUAGE')
def test_directive_for_foreign_scene(tmp_path):
    repo, story, scene, draft = world(tmp_path, language='uk', prose_language='en')
    draft_context = build_context(repo, scene.id, 'draft', role())
    assert 'Пиши прозу цієї сцени англійською мовою.' in draft_context.system_text
    for stage in ['brief', 'memory']:
        assert 'Пиши прозу цієї сцени' not in build_context(repo, scene.id, stage, role()).system_text


@pytest.mark.req('STORY-LANGUAGE')
def test_directive_for_ukrainian_scene_in_english_story(tmp_path):
    repo, story, scene, draft = world(tmp_path, language='en', prose_language='uk')
    assert "Write this scene's prose in Ukrainian." in build_context(repo, scene.id, 'edit', role()).system_text


@pytest.mark.req('STORY-LANGUAGE')
def test_no_directive_when_languages_match(tmp_path):
    repo, story, scene, draft = world(tmp_path, language='en', prose_language='en')
    system = build_context(repo, scene.id, 'draft', role()).system_text
    assert 'Write this scene' not in system


def test_day_label_english():
    assert day_label('day:3', 'en') == 'day 3'
    assert day_label('day:3') == 'день 3'


def english_cards(repo, story, entries):
    import json
    cards = [dict(schema_version=2, id=cid, name=name, entries=[dict(id='e' + cid, text=text, availability='timeless', origin='author')])
             for cid, name, text in entries]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('stage', ['brief', 'draft', 'memory'])
def test_english_request_with_character_cards_has_no_cyrillic(tmp_path, stage):
    repo, story, scene, draft = world(tmp_path, cards=[('A', 'Anna', 'A lighthouse keeper.')])
    context = build_context(repo, scene.id, stage, role())
    assert 'CHARACTER CARDS' in context.user_text or stage == 'memory'
    assert not CYRILLIC.search(texts(context))


@pytest.mark.req('STORY-LANGUAGE')
def test_acquaintance_block_follows_story_language(tmp_path):
    from storygen.characters.acquaintance import acquaintance_material
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='en'))
    # The protagonist marker is still recognised by its Ukrainian form (language hints are PR 2).
    english_cards(repo, story, [('A', 'Anna', 'Протагоністка'), ('B', 'Ben', 'Знайомий з: Anna')])
    scene = repo.create_scene(story.id, SceneCreate(title='Pier', character_ids=['A', 'B']))
    view = repo.context_view(story.id)
    text, _ = acquaintance_material(view, view.get_story(story.id), view.get_scene(scene.id), 'brief')
    assert text.startswith('WHOM THE PROTAGONIST KNOWS — Anna')
    assert 'Known: Ben (before the story begins)' in text
    assert not CYRILLIC.search(text)


@pytest.mark.req('STORY-LANGUAGE')
def test_impact_and_publication_requests_english(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.dependency_models import DependencySelector
    from storygen.generation.dependencies import save_manual_prose
    from storygen.generation.impact_context import build_impact_context
    from storygen.generation.publication_metadata import build_publication_context
    from storygen.impact.planning import plan_impact
    from storygen.storage.snapshots import build_author_baseline
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='en'))
    first = repo.create_scene(story.id, SceneCreate(title='Morning', beats='Morning'))
    second = repo.create_scene(story.id, SceneCreate(title='Evening', beats='Evening'))
    a = save_manual_prose(repo, first.id, 'Mary knows about the letter.', 0)
    snapshot = build_author_baseline(repo.context_view(story.id), second.id)
    snapshot.selectors.append(DependencySelector(kind='head', owner_id=first.id, field='prose', expected=a.id))
    snapshot.refs[a.id] = a.sha256
    ref = repo.save_version(story.id, second.id, 'edited', 'Mary remembered the letter.', list(snapshot.refs), dependency_snapshot=snapshot)
    repo.set_head(second.id, 'prose', ref.id, repo.get_scene(second.id).revision)
    save_manual_prose(repo, first.id, 'Mary does not know about the letter.', repo.get_scene(first.id).revision)
    planner = RoleSettings(provider=ProviderSettings(model='planner-test', response_mode='json_schema'), context_tokens=128000,
                           max_input_chars=1000000, max_output_tokens=2048)
    save_role_settings(repo, story.id, 'planner', planner, repo.get_story(story.id).revision)
    target = next(t for t in plan_impact(repo.context_view(story.id)).targets if t.version_id == ref.id)
    for stage in ['impact_delta', 'impact_check']:
        context = build_impact_context(repo, target.model_dump(), stage)
        assert not CYRILLIC.search(texts(context)), stage
    other = Repository(tmp_path / 'publication')
    fresh = other.create_story(StoryCreate(title='Tide', language='en'))
    save_role_settings(other, fresh.id, 'planner', planner, fresh.revision)
    for title in ['Morning', 'Evening']:
        save_manual_prose(other, other.create_scene(fresh.id, SceneCreate(title=title)).id, f'{title} at the pier.', 0)
    publication = build_publication_context(other, fresh.id)
    assert not CYRILLIC.search(texts(publication))


@pytest.mark.req('STORY-LANGUAGE')
def test_field_labels_follow_story_language():
    assert label('field_canon_version_id', 'uk') == 'Канон'
    assert label('field_canon_version_id', 'en') == 'Canon'
    assert horizon_instructions(SimpleNamespace(position=0), 2, 'en').startswith('LIMITS OF THE CURRENT SCENE')


@pytest.mark.req('STORY-LANGUAGE')
def test_prepare_request_english(tmp_path):
    from storygen.authoring.imports import SourceFile, import_sources
    from storygen.generation.pipeline import prepare_context
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='en'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=b'Anna waits at the pier for a ship.', kind='source_plan')])
    context = prepare_context(repo, story.id, role())
    assert 'AUTHOR SOURCE [version_id=' in context.user_text
    assert not CYRILLIC.search(texts(context))


@pytest.mark.req('STORY-LANGUAGE')
def test_edit_loop_patches_request_english(tmp_path):
    from storygen.generation import editor_loop
    repo, story, scene, draft = world(tmp_path)
    context = editor_loop.context(repo, scene.id, role(edit_mode='patches'), draft.id)
    assert 'DRAFT [version_id=' in context.user_text
    assert not CYRILLIC.search(texts(context))


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('language', ['uk', 'en'])
def test_review_basis_note_follows_plan_language(language):
    from storygen.review.wire import request_for
    plan = {'registry': {'t1': {'kind': 'target', 'text': 'Text.', 'material': 'prose', 'version_id': 'v1'}},
            'basis_modes': {'v1': 'current_consistency'}, 'result_cap': 2000}
    if language == 'en':
        plan['language'] = 'en'
    spec = {'phase': 'check', 'source_refs': [], 'target_refs': ['t1'], 'rule_ids': [], 'dependencies': [],
            'settings': role().model_dump(), 'system': 'System.'}
    payload, body, aliases = request_for(plan, spec, {})
    assert payload['basis_note'] == label('review_basis_note', language)
    assert bool(CYRILLIC.search(payload['basis_note'])) == (language == 'uk')


@pytest.mark.req('STORY-LANGUAGE')
def test_classifier_prompt_english_has_no_cyrillic():
    from storygen.generation.edit_classification import PROMPT, PROMPT_EN
    assert not CYRILLIC.search(PROMPT_EN) and CYRILLIC.search(PROMPT)
