"""EDIT-SENTENCE-GROUPS-S04/S05: parts of a sentence group and selection of a group the author split."""
import pytest

from storygen.rewrite_diff import build_rewrite_diff
from storygen.sentence_groups import SPLIT_ERROR, sentence_groups, validate_group_selection

SOURCE = 'Boris скинув важкий робочий жилет на стілець та розстібнув комір комбінезона, що з тихим шелестом відійшов від шкіри.'
CANDIDATE = 'Борис скинув важкий робочий жилет на стілець і розстебнув комір комбінезона; тканина з тихим шелестом відійшла від шкіри.'
GROUP_ERROR = 'Взаємозалежні правки речення'


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
def test_each_edit_of_a_sentence_is_a_part_with_its_index():
    proposal = build_rewrite_diff(SOURCE, CANDIDATE)
    assert [edit.original for edit in proposal.edits] == ['Boris', 'та розстібнув комір комбінезона, що з тихим шелестом відійшов']
    (group,) = sentence_groups(SOURCE, proposal)
    assert group['indices'] == [0, 1] and group['units'] == [[0], [1]]
    assert [part.get('index') for part in group['before_parts'] if part['changed']] == [0, 1]
    assert [part.get('index') for part in group['after_parts'] if part['changed']] == [0, 1]
    assert all('index' not in part for part in group['after_parts'] if not part['changed'])


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
def test_only_a_split_group_accepts_whole_parts():
    proposal = build_rewrite_diff(SOURCE, CANDIDATE)
    # An old client without split_groups: the sentence is still all or nothing.
    with pytest.raises(ValueError, match=GROUP_ERROR):
        validate_group_selection(SOURCE, proposal, [1])
    validate_group_selection(SOURCE, proposal, [1], split=[0])
    validate_group_selection(SOURCE, proposal, [], split=[0])
    validate_group_selection(SOURCE, proposal, [0, 1], split=[0])


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
@pytest.mark.parametrize('split', [[1], [7]])
def test_split_must_name_a_group_with_several_parts(split):
    proposal = build_rewrite_diff(SOURCE, CANDIDATE)
    with pytest.raises(ValueError) as error:
        validate_group_selection(SOURCE, proposal, [0, 1], split=split)
    assert str(error.value) == SPLIT_ERROR


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
def test_single_part_group_cannot_be_split():
    before, after = 'Вона йшов додому.', 'Вона йшла додому.'
    proposal = build_rewrite_diff(before, after)
    (group,) = sentence_groups(before, proposal)
    assert group['units'] == [[0]]
    with pytest.raises(ValueError) as error:
        validate_group_selection(before, proposal, [0], split=[0])
    assert str(error.value) == SPLIT_ERROR


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
def test_overlapping_markdown_dependencies_form_one_part():
    from storygen.markdown_document import format_dependency_groups
    before = '**' + 'Alpha ' * 8 + '*' + 'beta ' * 8 + '* gamma**.'
    after = 'Alpha ' * 8 + 'beta ' * 8 + ' gamma.'
    proposal = build_rewrite_diff(before, after)
    assert len(proposal.edits) == 3
    units = [dict(index=i, start=e.start, end=e.end, replacement=e.replacement) for i, e in enumerate(proposal.edits)]
    assert sorted(map(sorted, format_dependency_groups(before, after, units))) == [[0, 2], [1, 2]]
    (group,) = sentence_groups(before, proposal, 'markdown')
    assert group['units'] == [[0, 1, 2]]
    with pytest.raises(ValueError) as error:
        validate_group_selection(before, proposal, [0, 1, 2], 'markdown', split=[0])
    assert str(error.value) == SPLIT_ERROR


@pytest.mark.req('EDIT-SENTENCE-GROUPS')
def test_markdown_part_stays_whole_in_a_split_group():
    before = 'Boris скинув **важкий робочий жилет на стілець і довго дивився у вікно** на станції, де світло вже гасло.'
    after = 'Борис скинув важкий робочий жилет на стілець і довго дивився у вікно на станції, де світло вже згасало.'
    proposal = build_rewrite_diff(before, after)
    assert [edit.original for edit in proposal.edits] == ['Boris скинув **', '**', 'гасло']
    (group,) = sentence_groups(before, proposal, 'markdown')
    # The opening and closing bold markers belong to edits 0 and 1: one part.
    assert group['units'] == [[0, 1], [2]]
    validate_group_selection(before, proposal, [2], 'markdown', split=[0])
    validate_group_selection(before, proposal, [0, 1], 'markdown', split=[0])
    with pytest.raises(ValueError, match=GROUP_ERROR):
        validate_group_selection(before, proposal, [1, 2], 'markdown', split=[0])
