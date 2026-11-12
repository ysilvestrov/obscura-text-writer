"""MEMORY-SUMMARY-S02 (pure selection): a usable summary replaces its whole block inside the selection budget."""
from storygen.memory.projection import MemoryItem, render_memory
from storygen.memory.selection import SelectionInput, select_memory
from storygen.memory.summaries import StaleSummary, SummaryCandidate


def timeline(number):
    return MemoryItem(f't{number}', 'timeline', None, f'— Сцена {number}: Подія номер {number} у місті', f'Подія номер {number} у місті',
                      (), None, number)


CORE = MemoryItem('core', 'core', 'h', 'місце: Дім', 'Дім', ('h',), 'місце', None)


def inp(scene=23, summaries=(), stale=(), count=22):
    items = (CORE,) + tuple(timeline(n) for n in range(1, count + 1))
    return SelectionInput(items, 's', scene, ('h',), ('h',), {'h': 'Ганна'}, summaries=tuple(summaries), stale_summaries=tuple(stale))


FIRST = SummaryCandidate('range:1-10', 'v1', 1, 10, '— Підсумок сцен 1–10: Ганна приїхала й оселилася.')
SECOND = SummaryCandidate('range:11-20', 'v2', 11, 20, '— Підсумок сцен 11–20: Ганна знайшла роботу.')


def test_summary_replaces_the_whole_block_and_is_not_counted():
    result = select_memory(inp(summaries=[FIRST]), 2000)
    assert result.summaries == (('range:1-10', 'v1'),)
    chosen = set(result.selected_claim_ids)
    assert not chosen & {f't{n}' for n in range(1, 11)}
    assert {f't{n}' for n in range(11, 23)} <= chosen
    assert result.dropped['timeline'] == 0 and result.timeline_note is None
    assert 'Підсумок сцен 1–10' in result.text and 'Сцена 3:' not in result.text
    assert result.layers['summary'] == 1


def test_render_order_note_then_summaries_then_entries():
    full = render_memory([CORE] + [timeline(n) for n in range(1, 23)], ['h'], {'h': 'Ганна'})
    result = select_memory(inp(scene=33, summaries=[SECOND], count=32), len(full))
    lines = result.text.split('ХРОНОЛОГІЯ')[1].strip().splitlines()
    assert lines[0].startswith('— Не показано записів: 10')
    assert lines[1].startswith('— Підсумок сцен 11–20') and lines[2].startswith('— Сцена 21:')
    no_note = select_memory(inp(summaries=[FIRST]), 2000).text.split('ХРОНОЛОГІЯ')[1].strip().splitlines()
    assert no_note[0].startswith('— Підсумок сцен 1–10') and no_note[1].startswith('— Сцена 11:')


def test_tight_budget_takes_the_later_block_first_and_an_unfit_summary_returns_its_entries():
    from storygen.memory.selection import minimal_chars
    budget = minimal_chars(inp(scene=33, count=32)) + len(SECOND.line) + 1 + 30
    result = select_memory(inp(scene=33, summaries=[FIRST, SECOND], count=32), budget)
    assert result.summaries == (('range:11-20', 'v2'),)
    # The first summary did not fit: its block lies beyond the window, so its entries are counted by the note, never shown.
    assert result.timeline_note.startswith('Не показано записів:') and '1–10' in result.timeline_note
    assert 'Сцена 3:' not in result.text and result.dropped['summary'] == 1


def test_trimmed_summary_counts_its_block_once():
    long_first = SummaryCandidate('range:1-10', 'v1', 1, 10, '— Підсумок сцен 1–10: ' + 'дуже довгий опис ' * 60)
    result = select_memory(inp(summaries=[long_first]), 900)
    assert result.summaries == ()
    total = sum(result.layers.values()) - result.layers['core'] + sum(result.dropped.values())
    assert total == 22 + 1  # every timeline entry once, plus the summary itself


def test_stale_head_with_dropped_entries_warns():
    stale = StaleSummary('range:1-10', 1, 10, 'stale')
    result = select_memory(inp(stale=[stale]), 2000)
    assert result.warnings == ('Підсумок сцен 1–10 застарів: перебудуйте його в панелі пам’яті.',)
    assert select_memory(inp(scene=11, stale=[stale], count=10), 2000).warnings == ()


def test_no_summary_keeps_the_selection_unchanged():
    plain = select_memory(inp(), 1500)
    assert plain.summaries == () and plain.warnings == () and plain.layers['summary'] == 0
