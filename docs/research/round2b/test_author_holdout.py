"""Only invented unit fixtures; never read the private research corpus."""
import pytest
import json
from pathlib import Path
from round2b import author_holdout as module
from round2b.author_holdout import (words, mechanical_case, check_pair,
                                    blind_order, render_blind, validate_structure)


def case(**changes):
    row = dict(id='fixture-neutral-a', template='fixture', family='B',
               context='neutral', variant='a', characters=['Ніна'], frame_names=['Ніна'],
               sources=['Персонажі епізоду: Ніна (30 років). Вона працює над фотографіями міських будівель. Інші події прямо задані окремими передумовами.', 'Ручка має металевий ковпачок.'],
               target='Ніна покрутила ручку в долоні.',
               gold=dict(verdict='clean', contradictions=[], clean_reason='Сумісно.', question_reason=''))
    return row | changes


def test_word_normalization():
    assert words('П’ЯТЬ, п\'ять — пʼять!') == ['п’ять'] * 3


def test_frame_agrees_with_number():
    one = module.frame(['Ніна'], 'adult')
    assert 'Вона бере участь' in one
    assert 'Усі учасники повнолітні й погодили межі зйомки.' in one
    assert 'Вони' not in one
    assert 'Вони беруть участь' in module.frame(['Ніна', 'Ігор'], 'adult')
    assert 'Вона працює' in module.frame(['Ніна'], 'neutral')
    assert 'Вони працюють' in module.frame(['Ніна', 'Ігор'], 'neutral')


def test_revision_separates_recheck_and_preserves_other_annotations():
    rows = [case(id=f'private-{i}', template=f'secret-{i}') for i in range(3)]
    review = dict(items=[
        dict(position=1, status='recheck', annotation='- [x] issue\n- Зауваження: old.'),
        dict(position=2, status='frame_only', annotation='- [x] clean\n- Коментар: зберегти.'),
        dict(position=3, status='unchanged', annotation='- [x] question\n- Коментар: інший.')])
    panel = module.render_revision(rows, 'Промпт.', review)
    first = panel.index('## Повторно оцінити')
    second = panel.index('## Лише виправлення рамки')
    third = panel.index('## Без змін')
    assert first < panel.index('### Приклад 01') < second < panel.index('### Приклад 02') < third < panel.index('### Приклад 03')
    assert '- [x] issue' not in panel
    assert '- [x] clean\n- Коментар: зберегти.' in panel
    assert '- [x] question\n- Коментар: інший.' in panel
    assert 'old.' not in panel and 'secret-' not in panel and 'private-' not in panel


def test_accept_mechanically_safe_fixture():
    assert mechanical_case(case()) is None


@pytest.mark.parametrize('phrase', ['А не срібло.', 'Вперше в житті.', 'Ніколи.',
                                  'Не чіпаючи замок.', 'Саме той.', 'Тієї єдиної.'])
def test_banned_constructs(phrase):
    with pytest.raises(ValueError, match='banned'):
        mechanical_case(case(target=phrase))


def test_fourgram_ignores_case_and_punctuation():
    with pytest.raises(ValueError, match='4gram'):
        mechanical_case(case(target='РУЧКА, має: металевий — ковпачок!'))


def test_extra_frame_name():
    with pytest.raises(ValueError, match='frame'):
        mechanical_case(case(frame_names=['Ніна', 'Богдан']))


def test_frame_name_must_appear_outside_frame():
    with pytest.raises(ValueError, match='frame'):
        mechanical_case(case(target='Світло згасло.'))


def test_pair_one_change_and_length():
    a = case(target='Ніна взяла синю чашку зі столу.')
    b = case(variant='b', target='Ніна взяла білу чашку зі столу.')
    assert check_pair(a, b) is None
    with pytest.raises(ValueError, match='fragment'):
        check_pair(a, b | dict(target='Ніна поклала білу чашку під стіл.'))
    with pytest.raises(ValueError, match='length'):
        check_pair(a, b | dict(target='Ніна взяла надзвичайно велику порожню білу чашку зі столу.'))


def test_d_priority_changes_only_sources():
    a = case(family='D', sources=['Ніна тут.', 'Довга спільна передумова. ' * 12])
    b = a | dict(variant='b', sources=a['sources'] + ['Автор обрав А.'])
    assert check_pair(a, b) is None
    with pytest.raises(ValueError, match='D target'):
        check_pair(a, b | dict(target='Інший текст.'))


def test_shuffle_and_render_do_not_leak_labels():
    rows = [case(id=f'private-{t}-{v}', template=f'secret-{t}', variant=v)
            for t in range(12) for v in ('a', 'b', 'c', 'd')]
    ordered = blind_order(rows, 'unit-seed')
    assert ordered == blind_order(rows, 'unit-seed')
    assert all(a['template'] != b['template'] for a, b in zip(ordered, ordered[1:]))
    panel = render_blind(ordered, 'Тестовий промпт.')
    assert panel.count('- [ ] clean') == 48
    assert panel.count('Цитата для issue:') == 48
    assert 'private-' not in panel and 'secret-' not in panel
    assert 'Сумісно.' not in panel
    assert 'S1.' in panel and 'T1.' in panel


def test_reject_incomplete_design():
    with pytest.raises(ValueError):
        validate_structure([case()])


def quartet_templates():
    templates = []
    for family, number in module.FAMILIES.items():
        for i in range(number):
            a = f'Ніна розглянула предмет{family}{i} біля лампи й узяла синю чашку.'
            b = a.replace('синю', 'білу')
            if family == 'D': b = a
            gold = {}
            for v in ('a', 'b'):
                verdict = ('question' if v == 'a' else 'clean') if family == 'D' else 'issue' if family == 'E' or v == 'b' else 'clean'
                n = 2 if family == 'E' and v == 'a' else int(verdict == 'issue')
                facts = [dict(id=f'g{j}', type='test', severity='major', source_indices=[1], target_quote='Ніна') for j in range(n)]
                gold[v] = dict(verdict=verdict, contradictions=facts, clean_reason='Тест.', question_reason='Тест?')
            templates.append(dict(id=f'{family}{i}', family=family, characters=['Ніна'],
                sources=['Ніна оглядає предмет. На столі стоїть посуд. ' * 8], a=a, b=b,
                gold=gold, **({'priority':'Автор обрав А.'} if family == 'D' else {})))
    return templates


def test_full_structure_and_bad_family():
    import copy
    cases = module.make_cases(quartet_templates())
    assert validate_structure(cases) is None
    broken = copy.deepcopy(cases)
    broken[0]['family'] = 'D'
    with pytest.raises(ValueError): validate_structure(broken)
    broken = copy.deepcopy(cases)
    broken[0]['gold']['contradictions'] = [dict(id='bad')]
    with pytest.raises(ValueError): validate_structure(broken)


def write_fixture_bundle(folder):
    cases = module.make_cases(quartet_templates())
    order = blind_order(cases, 'test-seed')
    # Only the already public prompt is read; never the private holdout.
    prompt = (Path(module.__file__).parent/'prompts/check-aprime-v1-uk.txt').read_bytes()
    (folder/'prompts').mkdir()
    (folder/'prompts/check-aprime-v1-uk.txt').write_bytes(prompt)
    files = {'holdout-draft.json':module.encoded(cases),
        'oracle-key.json':module.encoded(dict(seed='test-seed', positions=[dict(position=i, case_id=r['id'], gold=r['gold']) for i,r in enumerate(order,1)])),
        'oracle-blind.md':render_blind(order,prompt.decode()).encode()}
    for name, data in files.items(): (folder/name).write_bytes(data)
    manifest = dict(files={n:module.sha(b) for n,b in files.items()}, source_sha256=module.sha(Path(module.__file__).read_bytes()))
    (folder/'manifest.json').write_bytes(module.encoded(manifest))
    return manifest


def test_bundle_integrity(tmp_path):
    write_fixture_bundle(tmp_path)
    assert module.self_check(tmp_path) == 48
    with (tmp_path/'oracle-blind.md').open('a',encoding='utf-8') as out: out.write('changed')
    with pytest.raises(ValueError, match='Changed stage-3 file'):
        module.self_check(tmp_path)


def test_changed_generator_rejected(tmp_path):
    manifest = write_fixture_bundle(tmp_path)
    manifest['source_sha256'] = '0' * 64
    (tmp_path/'manifest.json').write_bytes(module.encoded(manifest))
    with pytest.raises(ValueError, match='generator'):
        module.self_check(tmp_path)


def test_main_never_overwrites_panel(tmp_path, monkeypatch):
    import sys
    (tmp_path/'oracle-blind.md').write_text('owner marks', encoding='utf-8')
    monkeypatch.setattr(module, 'FOLDER', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['author', '--input', 'unused.json', '--author-model', 'test-author'])
    with pytest.raises(SystemExit, match='refusing to overwrite'):
        module.main()
    assert (tmp_path/'oracle-blind.md').read_text() == 'owner marks'


def test_revision_bundle_integrity_and_annotation_preservation(tmp_path):
    manifest = write_fixture_bundle(tmp_path)
    cases = json.loads((tmp_path/'holdout-draft.json').read_text(encoding='utf-8'))
    key = json.loads((tmp_path/'oracle-key.json').read_text(encoding='utf-8'))
    order = blind_order(cases, key['seed'])
    review = dict(items=[dict(position=i, status='recheck' if i==1 else 'unchanged',
                             annotation='- [x] clean\n- Коментар: оригінал.') for i in range(1,49)])
    data = module.encoded(review)
    (tmp_path/'review.json').write_bytes(data)
    prompt = (tmp_path/'prompts/check-aprime-v1-uk.txt').read_text(encoding='utf-8')
    panel = module.render_revision(order,prompt,review).encode('utf-8')
    (tmp_path/'oracle-blind.md').write_bytes(panel)
    manifest.update(review_revision_file='review.json')
    manifest['files'].update({'review.json':module.sha(data),'oracle-blind.md':module.sha(panel)})
    (tmp_path/'manifest.json').write_bytes(module.encoded(manifest))
    assert module.self_check(tmp_path) == 48
    assert panel.decode().count('- [x] clean')==47


@pytest.mark.parametrize('positions', [[1,1], [1,3]])
def test_revision_rejects_missing_or_duplicate_positions(positions):
    rows = [case(),case()]
    review = dict(items=[dict(position=i,status='unchanged',annotation='') for i in positions])
    with pytest.raises(ValueError, match='positions'):
        module.render_revision(rows,'Prompt',review)


def test_revision_rejects_adjacent_template_in_recheck_section():
    rows = [case(template=t) for t in ['X','Y','X','Z']]
    review = dict(items=[dict(position=i,status='recheck' if i in (1,3) else 'unchanged',
                             annotation='') for i in range(1,5)])
    with pytest.raises(ValueError, match='Adjacent template'):
        module.render_revision(rows,'Prompt',review)


def test_single_template_repair_is_explicit_and_versioned():
    rows = [case(template='X'),case(template='X')]
    review = dict(revision=3, original_annotation_archive='oracle-blind-v2-annotated.md',
                  single_template_repair=True,
                  items=[dict(position=i,status='recheck',annotation='') for i in (1,2)])
    panel=module.render_revision(rows,'Prompt',review)
    assert 'редакція 3' in panel and 'oracle-blind-v2-annotated.md' in panel
    assert 'точковий перегляд однієї групи' in panel
