"""STORY-LANGUAGE-S05: copyediting guards protect English numbers and negations too (#32)."""
import pytest

from storygen.copyediting import CopyEdit, CopyEdits, apply_copyedits, protected_negations, protected_numbers
from storygen.rewrite_diff import rewrite_warnings

TEXT = 'Anna had three keys. She did not go home. She didn\'t look back.'


def edit(original, replacement):
    return CopyEdits(edits=[CopyEdit(fragment_id='f000001', original=original, replacement=replacement, category='wording')])


@pytest.mark.req('STORY-LANGUAGE')
def test_english_number_change_rejected():
    with pytest.raises(ValueError, match='числовий факт'):
        apply_copyedits(TEXT, edit('three keys', 'four keys'))


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('original,replacement', [('did not go', 'did go'), ("didn't look", 'did look'), ('She did not', 'She never')])
def test_english_negation_removed_rejected(original, replacement):
    with pytest.raises(ValueError, match='заперечення'):
        apply_copyedits(TEXT, edit(original, replacement))


@pytest.mark.req('STORY-LANGUAGE')
def test_english_spelling_fix_allowed():
    assert apply_copyedits('Anna had three keyz.', edit('keyz', 'keys')) == 'Anna had three keys.'


@pytest.mark.req('STORY-LANGUAGE')
def test_rewrite_diff_warns_english_negation():
    warnings = rewrite_warnings('She did not go home.', 'She did go home.')
    assert 'Редактура змінює заперечення.' in warnings
    assert 'Редактура змінює числові факти.' in rewrite_warnings('three keys', 'four keys')


@pytest.mark.req('STORY-LANGUAGE')
def test_word_lists_are_a_union():
    assert protected_numbers('Їй сорок, she is forty, 1st of twenty') == ['сорок', 'forty', '1', 'twenty']
    assert protected_negations('не знала, nobody knew, won’t tell') == ['не', 'nobody', 'won’t']
