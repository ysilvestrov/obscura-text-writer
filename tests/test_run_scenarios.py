"""Checks of the skills' behaviour scenarios (CLAUDE-SKILLS S04–S09)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'integrations'/'claude'/'tools'))

from run_scenarios import (author_asked, author_problems, bible_problems, creation_problems, outcome_problems,  # noqa: E402
                           pipeline_problems,
                           publish_problems,
                           settings_problems, verdict, obscura_revise_problems, revise_chain_problems,
                           replacement_table_problems,
                           revise_preconsent_problems, revise_text_problems, check_preamble, revise_memory_problems,
                           sum_usage)
from revise_setup import NEW_STEM, OLD_STEM, _core_decisions, fixture_text  # noqa: E402
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
        'сцена 1: змінено речення без старого факту: «Пила чай.»', 'сцена 1: додано речення: «Пила каву.»']
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


@pytest.mark.req('CLAUDE-SKILLS')
def test_obscura_revise_paid_run_needs_its_own_consent():
    assert obscura_revise_problems([('start_run', {'action': 'memory'})]) == []
    assert obscura_revise_problems([('start_run', {'action': 'memory', 'confirm': True})]) == [
        "запущено платний запуск: ['memory']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_replacement_table_is_not_an_echo_of_the_request():
    echo = 'Перенеси дію з Одеси в Херсон? Добре, зроблю. Сцени «Лист» і «Четвер».'
    assert replacement_table_problems(echo, 'Одес', 'Херсон', ['Лист', 'Четвер']) == [
        'немає рядка таблиці з «Одес» і «Херсон»', 'сцена «Лист» не названа в таблиці',
        'сцена «Четвер» не названа в таблиці']
    table = ('| Сцена | Знайти | Замінити на |\n|---|---|---|\n| «Лист» | від Одеси | від Херсона |\n'
             '| «Четвер» | вогні Одеси | вогні Херсона |')
    assert replacement_table_problems(table, 'Одес', 'Херсон', ['Лист', 'Четвер']) == []
    assert replacement_table_problems(table, 'Одес', 'Херсон', ['Лист', 'Маяк']) == ['сцена «Маяк» не названа в таблиці']


@pytest.mark.req('CLAUDE-SKILLS')
def test_run_turns_pads_calls_when_first_turn_has_no_session(monkeypatch, tmp_path):
    import run_scenarios
    from types import SimpleNamespace
    names_seen = []

    def fake_run_claude(cmd, out):
        names_seen.append(Path(out).name)
        return Result(tool_calls=[('get_story', {})], is_error=False)

    monkeypatch.setattr(run_scenarios, 'run_claude', fake_run_claude)
    stand = SimpleNamespace(mcp_config=tmp_path/'m.json')
    result, turn_calls = run_scenarios.run_turns(['a', 'b'], stand, tmp_path, 'sonnet', 1)
    assert turn_calls == [[('get_story', {})], []] and result.is_error
    assert names_seen == ['run-1.jsonl']
    assert run_scenarios.revise_chain_problems(turn_calls[1], ['x'])
    run_scenarios.run_turns(['a'], stand, tmp_path, 'sonnet', 1)
    assert names_seen[-1] == 'run.jsonl'


@pytest.mark.req('CLAUDE-SKILLS')
def test_run_turns_keeps_each_turn_calls_apart(monkeypatch, tmp_path):
    import run_scenarios
    from types import SimpleNamespace
    turns = iter([Result(tool_calls=[('get_story', {})], errors=[('a', 'x')], session_id='s'),
                  Result(tool_calls=[('save_draft', {})], errors=[('b', 'y')], session_id='s')])
    monkeypatch.setattr(run_scenarios, 'run_claude', lambda cmd, out: next(turns))
    stand = SimpleNamespace(mcp_config=tmp_path/'m.json')
    result, turn_calls = run_scenarios.run_turns(['a', 'b'], stand, tmp_path, 'sonnet', 1)
    assert turn_calls == [[('get_story', {})], [('save_draft', {})]]
    assert result.tool_calls == [('get_story', {}), ('save_draft', {})]
    assert result.errors == [('a', 'x'), ('b', 'y')]
    assert run_scenarios.revise_preconsent_problems(turn_calls[0]) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_preconsent_flags_any_bridge_write():
    for name in ('update_story', 'update_settings', 'apply_role_preset', 'add_scene', 'import_plan_and_characters',
                 'export_book', 'update_plan_preamble', 'save_draft'):
        assert revise_preconsent_problems([('get_story', {}), (name, {})]) == [f"до згоди записано: ['{name}']"]
    assert revise_preconsent_problems([('start_run', {'action': 'memory'}), ('get_stage_task', {})]) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_text_header_line_is_separate():
    original = '## Сцена 1: Лист\nЛокація: пристань біля Одеси.\nПочаток: день 1'
    # A changed heading is its own sentence now, not merged into the location line that holds the old fact.
    assert revise_text_problems(original, '## Сцена 1: Лист!\nЛокація: пристань біля Херсона.\nПочаток: день 1',
                                'Одес', 'Херсон', 'план') == [
        'план: змінено речення без старого факту: «## Сцена 1: Лист»', 'план: додано речення: «## Сцена 1: Лист!»']
    # CRLF and trailing whitespace are not changes; whitespace inside a line is.
    assert revise_text_problems(original, '## Сцена 1: Лист  \r\nЛокація: пристань біля Херсона.\r\nПочаток: день 1',
                                'Одес', 'Херсон', 'план') == []
    assert revise_text_problems(original, '## Сцена 1:  Лист\nЛокація: пристань біля Херсона.\nПочаток: день 1',
                                'Одес', 'Херсон', 'план')[0] == 'план: змінено речення без старого факту: «## Сцена 1: Лист»'


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_text_added_sentence_is_a_problem():
    original = 'Жила в Одесі. Пила чай.'
    assert revise_text_problems(original, 'Жила в Херсоні. Пила чай. Там було гарно.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: додано речення: «Там було гарно.»']
    # A sentence with the new fact replaces one with the old fact: not an addition.
    assert revise_text_problems(original, 'Жила в Херсоні. Пила чай.', 'Одес', 'Херсон', 'сцена 1') == []
    # A repeated or dropped copy of an unchanged sentence counts.
    assert revise_text_problems(original, 'Жила в Херсоні. Пила чай. Пила чай.', 'Одес', 'Херсон', 'сцена 1') == [
        'сцена 1: додано речення: «Пила чай.»']
    assert revise_text_problems('Пила чай. Жила в Одесі. Пила чай.', 'Пила чай. Жила в Херсоні.', 'Одес', 'Херсон', 'с') == [
        'с: змінено речення без старого факту: «Пила чай.»']


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_chain_scene_order_is_checked():
    s1, s2 = 'a', 'b'

    def chain(scene):
        return [('save_stage_result', {'scene_id': scene, 'stage': st}) if st != 'draft' else ('save_draft', {'scene_id': scene})
                for st in ('brief', 'draft', 'edit', 'memory')]
    assert revise_chain_problems([('update_scene', {'scene_id': s2})] + chain(s1) + chain(s2), [s1, s2]) == []
    mixed = chain(s1)[:2] + chain(s2)[:1] + chain(s1)[2:] + chain(s2)[1:]
    assert revise_chain_problems(mixed, [s1, s2]) == ['сцена 2: записи до завершення сцени 1']
    assert revise_chain_problems(chain(s2) + chain(s1), [s1, s2]) == ['сцена 2: записи до завершення сцени 1']


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_preamble_is_part_of_the_text_check():
    original = 'Робоча назва: Маяк\nЗадум: Доглядачка маяка під Одесою.'
    story = {'plan_preamble': {'text': 'Робоча назва: Маяк\nЗадум: Доглядачка маяка під Херсоном.'}}
    assert check_preamble(original, story, 'Одес', 'Херсон') == []
    assert check_preamble(original, {'plan_preamble': {'text': original}}, 'Одес', 'Херсон') == [
        'преамбула плану: лишилося «Одес»', 'преамбула плану: немає «Херсон»']
    assert check_preamble(original, {}, 'Одес', 'Херсон')[0] == 'преамбула плану: немає «Херсон»'


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_memory_preserved_with_stem_replaced():
    old = [{'claim_id': 'mc_1', 'category': 'facts', 'text': 'Анна живе на маяку під Одесою.',
            'quote': 'Маяк стояв за кілька миль від Одеси, і пошту привозили по понеділках.', 'supporting_quotes': []}]
    new = [{'claim_id': 'mc_9', 'category': 'facts', 'text': 'Анна живе на маяку під Херсоном.',
            'quote': 'Маяк стояв за кілька миль від Херсона, і пошту привозили по понеділках.', 'supporting_quotes': []},
           {'claim_id': 'mc_10', 'category': 'character_states', 'text': 'Анна втомлена.', 'quote': 'Анна позіхнула.'}]
    assert revise_memory_problems(old, new, 'Одес', 'Херсон', 'сцена 1') == []
    reworded = [dict(new[0], text='Анна мешкає на маяку під Херсоном.')]
    assert revise_memory_problems(old, reworded, 'Одес', 'Херсон', 'сцена 1') == [
        "сцена 1: пам'ять не зберегла «Анна живе на маяку під Херсон….»"]
    assert revise_memory_problems(old, [], 'Одес', 'Херсон', 'сцена 1')


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_memory_check_never_passes_on_nothing():
    claim = [{'text': 'Анна живе під Херсоном.', 'quote': 'Біля Херсона.'}]
    assert revise_memory_problems([], claim, 'Одес', 'Херсон', 'x') == ["x: у старій пам'яті немає текстів і цитат для порівняння"]
    assert revise_memory_problems([{'claim_id': 'mc_1', 'text': '', 'quote': None}], claim, 'Одес', 'Херсон', 'x') == [
        "x: у старій пам'яті немає текстів і цитат для порівняння"]
    assert revise_memory_problems(claim, None, 'Одес', 'Херсон', 'x') == ["x: нову пам'ять не прочитано"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_revise_fixture_core_follows_the_day_change_rule():
    head = '{"names":{"c1":"Анна"},"core":{"c1":{"clothing":{},"carried":{},"location":{},"body":{},"company":{}}}}'
    material = 'ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ\n' + head + '\n\n'
    same_day = _core_decisions({'material': material})
    assert {d['status'] for d in same_day['c1'].values()} == {'unchanged'}
    changed = _core_decisions({'material': material + 'ЗМІНИВСЯ ДЕНЬ: день 1 → день 4 (Анна)\nОдяг…\n'})
    assert {slot for slot, d in changed['c1'].items() if d['status'] == 'unknown'} == {'clothing', 'carried', 'body'}
    assert all(changed['c1'][slot]['reason'] for slot in ('clothing', 'carried', 'body'))
    assert changed['c1']['location']['status'] == changed['c1']['company']['status'] == 'unchanged'


@pytest.mark.req('CLAUDE-SKILLS')
def test_run_turns_sums_usage(monkeypatch, tmp_path):
    import run_scenarios
    from types import SimpleNamespace
    first = {'input_tokens': 10, 'output_tokens': 5, 'service_tier': 'standard', 'cache_creation': {'ephemeral_5m_input_tokens': 2}}
    turns = iter([Result(usage=first, cost_usd=0.5, session_id='s'),
                  Result(usage={'input_tokens': 7, 'output_tokens': 1, 'cache_creation': {'ephemeral_5m_input_tokens': 3}},
                         cost_usd=0.25, session_id='s')])
    monkeypatch.setattr(run_scenarios, 'run_claude', lambda cmd, out: next(turns))
    result, _ = run_scenarios.run_turns(['a', 'b'], SimpleNamespace(mcp_config=tmp_path/'m.json'), tmp_path, 'sonnet', 1)
    assert result.usage == {'input_tokens': 17, 'output_tokens': 6, 'service_tier': 'standard',
                            'cache_creation': {'ephemeral_5m_input_tokens': 5}}
    assert result.cost_usd == 0.75 and first['input_tokens'] == 10
    assert sum_usage({}, None) == {}
