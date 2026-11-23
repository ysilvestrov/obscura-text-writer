from storygen.generation.broken_text import (
    broken_diff_edits, broken_patch, count_broken, drop_broken_suggestions, drop_diff_edits, known_words, new_broken_words, request_parts,
    stage_category, structured_broken,
)
from storygen.rewrite_diff import apply_rewrite_diff, build_rewrite_diff

R = '�'


def test_old_word_from_input_is_not_new_even_quoted_or_punctuated():
    known = known_words(f'Вона пахне ко{R}{R}и, як завжди.')
    assert new_broken_words(f'«ко{R}{R}и». І знову ко{R}{R}и!', known) == []


def test_new_word_is_reported_once_in_order():
    known = known_words('Котрась із рабинь тицяє пальцем.')
    assert new_broken_words(f'тицяє п{R}{R}льцем, п{R}{R}льцем і бул{R}{R}', known) == [f'п{R}{R}льцем', f'бул{R}{R}']


def test_bare_replacement_is_new_even_if_the_prompt_mentions_it():
    known = known_words('Кіт спить.', 'Відновіть слова з символом «�» за контекстом.')
    assert new_broken_words(f'кіт {R} спить', known) == [R]


def test_a_broken_one_letter_word_from_the_document_is_known():
    known = known_words(f'Він {R}{R} вона.', 'Відновіть слова з символом «�».')
    assert new_broken_words(f'Він {R}{R} вона пішли.', known) == []


def test_compact_json_and_escapes_in_the_request_do_not_glue_words():
    # Compact JSON as the request carries it: a key glued to the first word, an escaped U+FFFD, a literal "\n" escape.
    source = '{"mutable":[{"id":"c1","text":"ко\\ufffd\\ufffdи сидить у бібл' + R + R + 'отеці\\nба' + R + R + 'ня"}]}'
    known = known_words(source)
    assert known == {f'ко{R}{R}и', f'бібл{R}{R}отеці', f'ба{R}{R}ня'}
    assert new_broken_words(f'ко{R}{R}и у бібл{R}{R}отеці, ба{R}{R}ня', known) == []


def test_word_at_line_edges():
    assert new_broken_words(f'{R}{R}ранок\nвечір{R}{R}', known_words('ранок вечір')) == [f'{R}{R}ранок', f'вечір{R}{R}']


def test_count_broken():
    assert count_broken(f'a{R}{R}b {R}') == 3
    assert count_broken('чисто') == 0


def test_request_parts_split_instructions_from_the_document():
    body = {'messages': [{'role': 'system', 'content': 'перший'},
                         {'role': 'user', 'content': [{'type': 'text', 'text': 'другий'}]}]}
    assert request_parts(body) == ('перший', 'другий')


def test_publication_drops_damaged_fields_and_list_items():
    kept, dropped = drop_broken_suggestions(
        {'title': f'Ма{R}{R}к', 'annotation': 'Чиста анотація.', 'genres': ['драма', f'тр{R}{R}лер'], 'keywords': [f'с{R}{R}т']},
        frozenset())
    assert kept == {'annotation': 'Чиста анотація.', 'genres': ['драма']}
    assert dropped == 3


def test_structured_checks_decoded_strings():
    known = known_words(f'Стара ко{R}{R}и.')
    escaped = '{"text": "нове бу\\ufffd\\ufffdло"}'
    copied = '{"text":"ко��и"}'
    assert structured_broken(escaped, known) == [f'бу{R}{R}ло']
    assert structured_broken(copied, known) == []
    assert structured_broken('не json', known) == []


def test_diff_insertion_into_existing_word_is_broken():
    original = 'Сірий кіт спить. Сонце світить на вікно.'
    candidate = f'Сірий кіт{R} спить. Сонце світить на підвіконня.'
    proposal = build_rewrite_diff(original, candidate)
    bad = broken_diff_edits(original, proposal, known_words(original))
    assert len(bad) == 1
    kept = drop_diff_edits(original, proposal, bad)
    assert R not in kept.candidate_text
    assert 'підвіконня' in kept.candidate_text
    assert apply_rewrite_diff(original, kept) == kept.candidate_text


def test_patch_inside_a_word_is_judged_by_the_word_it_leaves():
    from storygen.copyediting import CopyEdit
    original = f'The cats slept on the windowsill. A note read {R}.'
    known = known_words(original)
    inside = CopyEdit(fragment_id='f000001', original='cat', replacement=R, category='grammar')
    fixing = CopyEdit(fragment_id='f000001', original=f'read {R}', replacement='read it', category='grammar')
    assert broken_patch(original, inside, known)
    assert not broken_patch(original, fixing, known)


def test_drop_all_edits_returns_none():
    original = 'Сірий кіт спить.'
    proposal = build_rewrite_diff(original, f'Сірий к{R}{R}т спить.')
    assert drop_diff_edits(original, proposal, broken_diff_edits(original, proposal, known_words(original))) is None


def test_stage_categories():
    assert stage_category('memory', 'prose') == 1
    assert stage_category('edit', 'diff') == 2
    assert stage_category('edit', 'patches') == 2
    assert stage_category('rewrite', 'prose') == 2
    assert stage_category('publication_suggest', 'prose') == 2
    assert stage_category('edit', 'prose') == 3
    assert stage_category('draft', 'prose') == 3
    assert stage_category('evaluate', 'prose') is None
