"""Checks of the skills' behaviour scenarios (CLAUDE-SKILLS S04–S09)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'integrations'/'claude'/'tools'))

from run_scenarios import (author_asked, author_problems, bible_problems, creation_problems, outcome_problems,  # noqa: E402
                           pipeline_problems,
                           publish_problems,
                           settings_problems, verdict, obscura_revise_problems, revise_chain_problems,
                           revise_preconsent_problems, revise_text_problems)
from revise_setup import NEW_STEM, OLD_STEM, fixture_text  # noqa: E402
from scripts.skills_stand import Result  # noqa: E402

CREATE = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {})]


@pytest.mark.req('CLAUDE-SKILLS')
def test_creation_alone_has_no_problems():
    assert creation_problems(CREATE) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_writing_scenes_after_creation_is_a_problem():
    calls = CREATE + [('save_draft', {}), ('save_stage_result', {'stage': 'brief'})]
    assert creation_problems(calls) == ["після створення записано тексти: ['save_draft', 'save_stage_result']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_patches_scenario_without_edit_is_a_problem_not_a_crash():
    calls = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {})]
    assert pipeline_problems(calls, state='draft', patches=True) == ['edit не збережено']


@pytest.mark.req('CLAUDE-SKILLS')
def test_memory_after_edit_awaiting_review_is_a_problem():
    calls = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {}), ('save_stage_result', {'stage': 'edit'}),
             ('save_stage_result', {'stage': 'memory'})]
    assert pipeline_problems(calls, state='needs_review', patches=True) == ["пам'ять після правок, що чекають перегляду автора"]


FULL = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {}), ('save_stage_result', {'stage': 'edit'}),
        ('save_stage_result', {'stage': 'memory'})]


@pytest.mark.req('CLAUDE-SKILLS')
def test_attempted_saves_without_finished_prose_are_a_problem():
    assert pipeline_problems(FULL, state='draft', patches=False) == ['сцена не дійшла до прози: стан draft']
    assert pipeline_problems(FULL[2:3], state='no_text', patches=True) == ['сцена не дійшла до правок: стан no_text']


@pytest.mark.req('CLAUDE-SKILLS')
def test_failed_claude_session_never_passes():
    failed = Result(tool_calls=[], cost_usd=0.0, usage={}, text='Requested model is unavailable', is_error=True, errors=[])
    assert verdict([], failed) == ['сесія claude завершилась помилкою']
    ok = Result(tool_calls=[], cost_usd=0.0, usage={}, text='done', is_error=False, errors=[])
    assert verdict([], ok) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_without_author_never_sets_one():
    calls = [('get_publication', {}), ('update_publication', {'fields': {'author_ids': ['x']}})]
    assert publish_problems(calls, author_given=False, palette=None) == ['автора записано без відповіді автора']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_without_author_never_adds_a_signature():
    assert publish_problems([('add_signature', {'display_name': 'Хтось'})], author_given=False, palette=None) ==         ['автора записано без відповіді автора']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_cover_uses_the_named_palette():
    calls = [('add_signature', {'display_name': 'Ірина Коваль'}), ('update_publication', {'fields': {'author_ids': ['s1']}}),
             ('generate_cover', {'palette': 'ink'}), ('update_publication', {'fields': {'cover_id': 'c1'}})]
    assert publish_problems(calls, author_given=True, palette='forest') == ["обкладинка не в палітрі forest: ['ink']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_cover_must_be_set_on_the_card():
    calls = [('update_publication', {'fields': {'author_ids': ['s1']}}), ('generate_cover', {'palette': 'forest'})]
    assert publish_problems(calls, author_given=True, palette='forest') == ['обкладинку не поставлено в картку']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_with_cover_set_has_no_problems():
    calls = [('update_publication', {'fields': {'author_ids': ['s1']}}), ('generate_cover', {'palette': 'forest'}),
             ('update_publication', {'fields': {'cover_id': 'c1'}})]
    assert publish_problems(calls, author_given=True, palette='forest') == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_key_pasted_in_chat_means_no_settings_writes():
    calls = [('get_settings', {}), ('update_settings', {'section': 'writer', 'fields': {'provider': 'openrouter', 'model': 'm'}})]
    assert settings_problems(calls, roles_after={}, catalog_ids=None) == ['налаштування змінено, хоча ключ мав іти в інтерфейс']


@pytest.mark.req('CLAUDE-SKILLS')
def test_configured_role_with_model_missing_from_catalog_is_a_problem():
    calls = [('update_settings', {'section': 'writer'}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {'writer': {'provider': 'openrouter', 'model': 'gone/model'}}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) ==         ['роль writer: моделі gone/model немає в каталозі openrouter']


@pytest.mark.req('CLAUDE-SKILLS')
def test_roles_written_without_any_check_are_a_problem():
    roles = {'writer': {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash'}}
    assert settings_problems([('update_settings', {'section': 'writer'})], roles_after=roles,
                             catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) == ['жодної звірки з каталогом (models_for_role)']


@pytest.mark.req('CLAUDE-SKILLS')
def test_recipe_with_same_writer_and_editor_is_a_problem():
    calls = [('update_settings', {})] + [('get_settings', {'models_for_role': r}) for r in ('planner', 'writer', 'editor', 'memory')]
    roles = {role: {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash'} for role in ('planner', 'writer', 'editor', 'memory')}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) ==         ['письменник і редактор — одна модель']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_created_before_consent_is_a_problem():
    assert bible_problems([('create_story', {})], None, consent=False) == ['біблію створено до згоди з переліком статей']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_with_consent_must_be_marked_as_bible():
    calls = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {})]
    assert bible_problems(calls, {'title': 'Маяки', 'number': None, 'bible': False}, consent=True) == ['твір не позначено як біблію серії']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_with_consent_writes_no_articles():
    calls = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {}), ('save_draft', {})]
    assert bible_problems(calls, {'title': 'Маяки', 'number': None, 'bible': True}, consent=True) ==         ["після створення записано тексти: ['save_draft']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_role_left_with_the_default_window_is_a_problem():
    calls = [('update_settings', {}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {'writer': {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash', 'context_tokens': 8192}}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) == \
        ['роль writer: context_tokens 8192 — менше 32768, сцени не вмістяться']


@pytest.mark.req('CLAUDE-SKILLS')
def test_partial_recipe_is_a_problem():
    calls = [('update_settings', {}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {'writer': {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash', 'context_tokens': 131072}}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}, all_roles=True) == \
        ['не налаштовано ролі: editor, memory, planner']


@pytest.mark.req('CLAUDE-SKILLS')
def test_every_configured_role_must_be_checked():
    calls = [('update_settings', {}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {role: {'provider': 'openrouter', 'model': model, 'context_tokens': 131072}
             for role, model in (('writer', 'a/w'), ('editor', 'a/e'))}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'a/w', 'a/e'}}) == \
        ['роль editor не звірено з каталогом (models_for_role)']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_author_must_be_the_named_one():
    card = {'author_ids': ['s2']}
    signatures = [{'id': 's1', 'display_name': 'Ірина Коваль'}, {'id': 's2', 'display_name': 'Олена Мирна'}]
    assert author_problems(card, signatures, 'Ірина Коваль') == ["автори картки ['Олена Мирна'], а не Ірина Коваль"]
    assert author_problems({'author_ids': ['s1']}, signatures, 'Ірина Коваль') == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_author_question_is_required():
    assert author_asked([], 'Як чинити з другою сценою?') is False
    assert author_asked([], 'Чиє ім’я поставити автором?') is True
    assert author_asked([('AskUserQuestion', {'questions': [{'question': 'Who is the author?'}]})], '') is True


@pytest.mark.req('CLAUDE-SKILLS')
def test_prose_without_saved_memory_is_a_problem():
    assert pipeline_problems(FULL, state='prose', patches=False, memory_saved=False) == ["пам'ять сцени не збережено"]
    assert pipeline_problems(FULL, state='prose', patches=False, memory_saved=True) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_outcome_needs_a_saved_cover_and_a_successful_export():
    calls = [('export_book', {'format': 'fb2'})]
    assert outcome_problems({'cover': None}, calls, [('export_book', 'Obscura відповіла 422')]) == \
        ['обкладинку не збережено в картці', 'жоден експорт не вдався']
    assert outcome_problems({'cover': {'id': 'c1'}}, calls + calls, [('export_book', '422')]) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_fixture_has_old_city_in_plan_and_both_scenes():
    for name in ('plan.md', 'prose-1.md', 'prose-2.md'):
        assert OLD_STEM in fixture_text(name)
        assert NEW_STEM not in fixture_text(name)
    assert sum(1 for line in fixture_text('plan.md').splitlines() if line.startswith('Локація:') and OLD_STEM in line) == 2
    for name in ('plan.md', 'prose-1.md', 'prose-2.md'):
        text = fixture_text(name)
        assert text.lower().count('одес') == text.count('Одес')
    for name in ('prose-1.md', 'prose-2.md'):
        assert 2 <= fixture_text(name).count('Одес') <= 3


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_preconsent_any_write_is_a_problem():
    assert revise_preconsent_problems([('get_story', {}), ('update_scene', {})]) == ["до згоди записано: ['update_scene']"]
    assert revise_preconsent_problems([('start_run', {'confirm': True})]) == ["до згоди записано: ['start_run']"]
    assert revise_preconsent_problems([('start_run', {'action': 'audit'})]) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_text_old_stem_in_any_case_is_a_problem():
    assert revise_text_problems('Жила в Одесі.', 'Жила в Одесі.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: лишилося «Одес»', 'сцена 1: немає «Херсон»']


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_text_changed_unrelated_sentence_is_a_problem():
    original = 'Жила в Одесі. Пила чай.'
    assert revise_text_problems(original, 'Жила в Херсоні. Пила каву.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: змінено речення без старого факту: «Пила чай.»']
    assert revise_text_problems(original, 'Жила в Херсоні. Пила чай.', 'Одес', 'Херсон', 'сцена 1') == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_chain_brief_before_draft_in_second_scene():
    s1, s2 = 'a', 'b'
    ok = [('save_stage_result', {'scene_id': s, 'stage': st}) if st != 'draft' else ('save_draft', {'scene_id': s})
          for s in (s1, s2) for st in ('brief', 'draft', 'edit', 'memory')]
    assert revise_chain_problems(ok, [s1, s2]) == []
    no_brief = [c for c in ok if not (c[1].get('scene_id') == s2 and c[1].get('stage') == 'brief')]
    assert revise_chain_problems(no_brief, [s1, s2]) == ['сцена 2: draft без нового brief']


@pytest.mark.req('CLAUDE-SKILLS')
def test_obscura_revise_plan_write_is_allowed():
    assert obscura_revise_problems([('update_scene', {}), ('update_plan_preamble', {})]) == []
    assert obscura_revise_problems([('save_draft', {})]) == ["у творі obscura записано текст: ['save_draft']"]
