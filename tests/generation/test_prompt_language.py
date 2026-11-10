"""STORY-LANGUAGE-S02: English stories get the English prompt set; Ukrainian prompts stay byte-for-byte (#32)."""
import hashlib
import json
import re
from importlib.resources import files
from types import SimpleNamespace

import pytest

from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.prompts import role_prompt
from storygen.language import PROMPTS, load_prompt
from storygen.prompt_contracts import brief_introduced_contract, expected_contract, markdown_preservation
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.rating.instructions import higher_scenes_block, rating_block
from storygen.storage.repository import Repository

CYRILLIC = re.compile('[Ѐ-ӿ]')

# SHA-256 prefixes of the Ukrainian prompts before #32; Ukrainian requests must not change.
UK_BASELINE = {
    'role:prepare': 'd33418790b6a0bb6',
    'role:brief': '3bbf05d8d1f606c2',
    'role:draft': 'ee176d3435113848',
    'role:edit:prose': '0fd7011ddea46d25',
    'role:edit:patches': '9cf2ba66dc672561',
    'role:edit:diff': 'fb0f6047d99b0aaf',
    'role:memory': 'eb1dc2403f01490f',
    'assisted_writer_v1': '3922abece0145c4a',
    'impact_check_v1': '862da22806b8833a',
    'impact_delta_v1': '6d166bd41dc2412b',
    'impact_part_v1': '2afbf480157cfdb7',
    'impact_part_v2': '76fc9ea4b7f7b003',
    'review_part_v3': '885140b1bee3bcba',
    'review_part_v4': 'a66666904d4e5073',
    'publication_metadata_v1': '437acd9305806407',
    'markdown': '765b0f5d1cdaeaf3',
    'brief_contract': 'd90e6ef926f0ffba',
    'rating': '48a7f1766c500c59',
    'higher': '59a3e391542ee0b6',
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def modes(edit_mode='prose'):
    return SimpleNamespace(edit_mode=edit_mode, memory_mode='evidence_delta')


def ukrainian_texts():
    out = {f'role:{stage}': role_prompt(stage, modes(), 'uk') for stage in ['prepare', 'brief', 'draft', 'memory']}
    out.update({f'role:edit:{mode}': role_prompt('edit', modes(mode), 'uk') for mode in ['prose', 'patches', 'diff']})
    out.update({key: load_prompt(key, 'uk') for key in UK_BASELINE if key in PROMPTS})
    out['markdown'] = markdown_preservation('uk')
    out['brief_contract'] = brief_introduced_contract('uk')
    out['rating'] = rating_block(ContentRating(sexual=1, violence=2, themes=0), 'uk')
    out['higher'] = higher_scenes_block([(2, ['sexual']), (4, ['violence', 'themes'])], 'uk')
    return out


@pytest.mark.req('STORY-LANGUAGE')
def test_ukrainian_prompts_unchanged():
    assert {key: digest(text) for key, text in ukrainian_texts().items()} == UK_BASELINE


@pytest.mark.req('STORY-LANGUAGE')
def test_registry_parity():
    resources = files('storygen.generation').joinpath('resources')
    for key, (package, name, languages) in PROMPTS.items():
        version = key.rsplit('_', 1)[1]
        assert 'uk' in languages, key
        for language in languages:
            text = files(package).joinpath('resources', f'{name}_{language}_{version}.txt').read_text(encoding='utf-8')
            if language == 'en':
                assert not CYRILLIC.search(text), f'{key}: Cyrillic in the English prompt'
    english = {path.name for path in resources.iterdir() if '_en_' in path.name}
    expected = {f'{name}_en_{key.rsplit("_", 1)[1]}.txt' for key, (package, name, languages) in PROMPTS.items()
                if 'en' in languages and package == 'storygen.generation'}
    assert english == expected


@pytest.mark.req('STORY-LANGUAGE')
def test_english_fragments_have_no_cyrillic():
    english = [role_prompt(stage, modes(), 'en') for stage in ['prepare', 'brief', 'draft', 'memory']]
    english += [role_prompt('edit', modes(mode), 'en') for mode in ['prose', 'patches', 'diff']]
    english += [markdown_preservation('en'), brief_introduced_contract('en'),
                rating_block(ContentRating(sexual=2, violence=1, themes=0), 'en'),
                higher_scenes_block([(2, ['sexual']), (4, ['violence', 'themes'])], 'en')]
    for text in english:
        assert text and not CYRILLIC.search(text)


@pytest.mark.req('STORY-LANGUAGE')
def test_evaluator_has_no_english_prompt():
    assert load_prompt('evaluator_v1', 'uk')
    with pytest.raises(ValueError):
        load_prompt('evaluator_v1', 'en')
    with pytest.raises(ValueError):
        load_prompt('no_such_v1', 'uk')


def english_story(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='en'))
    scene = repo.create_scene(story.id, SceneCreate(title='Arrival', beats='Anna waits at the pier.'))
    return repo, story, repo.get_scene(scene.id)


def role(**values):
    return RoleSettings(provider=ProviderSettings(model='test'), **{'context_tokens': 262144, **values})


@pytest.mark.req('STORY-LANGUAGE')
def test_english_story_gets_english_brief_prompt(tmp_path):
    repo, story, scene = english_story(tmp_path)
    context = build_context(repo, scene.id, 'brief', role())
    assert context.system_text.startswith(load_prompt('brief_v2', 'en'))
    assert not CYRILLIC.search(context.system_text)


@pytest.mark.req('STORY-LANGUAGE')
def test_custom_prompt_kept_in_english_story(tmp_path):
    repo, story, scene = english_story(tmp_path)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Anna waits.', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    settings = role(edit_mode='patches')
    prompt = repo.save_version(story.id, None, 'prompt', 'Власна редактура автора.', [],
                               prompt_contract=expected_contract('edit', settings))
    context = build_context(repo, scene.id, 'edit', settings.model_copy(update={'prompt_version_id': prompt.id}))
    assert context.system_text.startswith('Власна редактура автора.')


# SHA-256 prefixes of composed Ukrainian system messages, computed on 3d53405 (before #32) for this exact world.
UK_COMPOSED = {'brief': '461f1aa546cab9e0', 'draft': '5bd57f88e17b751b', 'edit:prose': 'eb3907d342e2fdfb',
               'edit:patches': 'f9f7d19f0998e104', 'edit:diff': 'f578ce5c8435b0e8', 'memory': 'eb1dc2403f01490f',
               'rewrite': 'e1fc4a0a52f7ad36'}


@pytest.mark.req('STORY-LANGUAGE')
def test_ukrainian_composed_system_messages_unchanged(tmp_path):
    from storygen.memory.journal import MemoryJournal, _add_event
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Маяк'))
    story = repo.update_story_rating(story.id, ContentRating(sexual=0, violence=1, themes=1), story.revision)
    first = repo.create_scene(story.id, SceneCreate(title='Дім', beats='Анна вдома.', character_ids=['A']))
    second = repo.create_scene(story.id, SceneCreate(title='Пристань', beats='Анна чекає.', character_ids=['A']))
    prose = repo.save_version(story.id, first.id, 'manual', 'Анна вдома.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=[_add_event('facts', 'Маяк на мапі', prose.id, 'вдома', 0)])
    memory = repo.save_version(story.id, first.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    brief = repo.save_version(story.id, second.id, 'brief', '{"objective":"Чекає","beats":["Чекає"],"constraints":[],"proposed_changes":[]}', [])
    repo.set_head(second.id, 'brief', brief.id, repo.get_scene(second.id).revision)
    draft = repo.save_version(story.id, second.id, 'draft', 'Анна чекала.', [brief.id])
    repo.set_head(second.id, 'draft', draft.id, repo.get_scene(second.id).revision)
    prose2 = repo.save_version(story.id, second.id, 'manual', 'Анна чекала.', [draft.id])
    repo.set_head(second.id, 'prose', prose2.id, repo.get_scene(second.id).revision)
    cases = {'brief': ('brief', {}), 'draft': ('draft', {}), 'edit:prose': ('edit', {}),
             'edit:patches': ('edit', {'edit_mode': 'patches'}), 'edit:diff': ('edit', {'edit_mode': 'diff'}),
             'memory': ('memory', {}), 'rewrite': ('rewrite', {})}
    found = {}
    for key, (stage, values) in cases.items():
        extra = {'editor_source_id': draft.id} if stage == 'rewrite' else {}
        found[key] = digest(build_context(repo, second.id, stage, role(**values), **extra).system_text)
    assert found == UK_COMPOSED
