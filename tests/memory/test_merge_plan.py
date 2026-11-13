"""MEMORY-MERGE-S01/S03/S05: conflicts, the merged journal and carried decisions (pure, neutral examples)."""
import pytest

from storygen.memory.journal import MemoryJournal, _add_event, _change_event, _extend, replay_memory
from storygen.memory.merge import Conflict, build_merged_journal, carry_decisions, plan_merge, shared_base

ORDER = ['h1', 'h2']
SOURCES = ['p0', 'p1', 'p2']  # p0 — the shared scene, p1 — head h1, p2 — head h2 (reading order)


def add(category, text, prose, *, characters=(), slot=None, occurrence=0):
    return _add_event(category, text, prose, f'«{text}»', occurrence, characters, slot=slot)


def change(action, claim, text, prose, *, category='character_states', characters=('c1',), slot=None):
    return _change_event(action, claim.claim_id, text, category, characters, prose, f'«{text}»', slot=slot)


def base_journal():
    events = [add('character_states', 'Анна в пальті', 'p0', characters=('c1',), slot='clothing'),
              add('open_threads', 'Лист не відправлено', 'p0'),
              add('facts', 'Місто стоїть на річці', 'p0')]
    return _extend(MemoryJournal(), 'p0', events)


def branch(base, prose, events):
    return _extend(base, prose, events)


def coat(base):
    return next(e for e in base.events if e.slot == 'clothing')


def letter(base):
    return next(e for e in base.events if e.category == 'open_threads')


def test_change_in_one_branch_merges_cleanly():
    base = base_journal()
    h1 = branch(base, 'p1', [add('facts', 'Анна купила квиток', 'p1')])
    h2 = branch(base, 'p2', [change('update', letter(base), 'Лист відправлено', 'p2', category='open_threads', characters=())])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    assert plan.conflicts == [] and len(plan.clean_events) == 2
    journal = build_merged_journal(plan, {}, SOURCES, 'p2')
    active = replay_memory(journal)
    assert active[letter(base).claim_id].text == 'Лист відправлено'
    assert any(e.text == 'Анна купила квиток' for e in active.values())


def test_different_updates_of_one_record_conflict():
    base = base_journal()
    h1 = branch(base, 'p1', [change('update', letter(base), 'Лист у кишені', 'p1', category='open_threads', characters=())])
    h2 = branch(base, 'p2', [change('update', letter(base), 'Лист спалено', 'p2', category='open_threads', characters=())])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    assert [(c.key, c.values) for c in plan.conflicts] == [(f'claim:{letter(base).claim_id}', {'h1': 'Лист у кишені', 'h2': 'Лист спалено'})]


def test_same_result_in_two_branches_is_not_a_conflict():
    base = base_journal()
    h1 = branch(base, 'p1', [change('retire', letter(base), 'Лист більше не важливий', 'p1', category='open_threads', characters=())])
    h2 = branch(base, 'p2', [change('retire', letter(base), 'Лист забуто', 'p2', category='open_threads', characters=())])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    assert plan.conflicts == []
    journal = build_merged_journal(plan, {}, SOURCES, 'p2')
    assert [e.operation for e in journal.events].count('retire') == 1


def test_two_new_records_of_one_slot_conflict():
    base = base_journal()
    h1 = branch(base, 'p1', [change('retire', coat(base), 'Анна зняла пальто', 'p1', slot='clothing'),
                             add('character_states', 'Анна в сукні', 'p1', characters=('c1',), slot='clothing')])
    h2 = branch(base, 'p2', [change('retire', coat(base), 'Анна зняла пальто', 'p2', slot='clothing'),
                             add('character_states', 'Анна в светрі', 'p2', characters=('c1',), slot='clothing')])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    assert [(c.key, c.values) for c in plan.conflicts] == [('slot:c1:clothing', {'h1': 'Анна в сукні', 'h2': 'Анна в светрі'})]
    assert not any(e.slot for e in plan.clean_events)


def test_retire_against_update_conflicts():
    base = base_journal()
    h1 = branch(base, 'p1', [change('retire', letter(base), 'Лист загубився', 'p1', category='open_threads', characters=())])
    h2 = branch(base, 'p2', [change('update', letter(base), 'Лист у сумці', 'p2', category='open_threads', characters=())])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    assert plan.conflicts[0].values == {'h1': None, 'h2': 'Лист у сумці'}
    assert plan.clean_events == []


def test_branch_choice_builds_valid_journal():
    base = base_journal()
    h1 = branch(base, 'p1', [change('update', coat(base), 'Анна в куртці', 'p1', slot='clothing')])
    h2 = branch(base, 'p2', [change('update', coat(base), 'Анна в плащі', 'p2', slot='clothing')])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    journal = build_merged_journal(plan, {'slot:c1:clothing': {'choice': 'h2'}}, SOURCES, 'p2')
    assert replay_memory(journal)[coat(base).claim_id].text == 'Анна в плащі'
    assert not any(e.text == 'Анна в куртці' for e in journal.events)
    assert journal.source_prose_ids == SOURCES


def test_author_value_event_cites_latest_head():
    base = base_journal()
    h1 = branch(base, 'p1', [change('update', coat(base), 'Анна в куртці', 'p1', slot='clothing')])
    h2 = branch(base, 'p2', [change('update', coat(base), 'Анна в плащі', 'p2', slot='clothing')])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    journal = build_merged_journal(plan, {'slot:c1:clothing': {'choice': 'author', 'text': 'Анна в дощовику'}}, SOURCES, 'p2')
    event = journal.events[-1]
    assert (event.source_kind, event.quote, event.source_version_id, event.text) == ('author', None, 'p2', 'Анна в дощовику')
    assert replay_memory(journal)[coat(base).claim_id].text == 'Анна в дощовику'


def test_author_empty_value_retires_the_base_record():
    base = base_journal()
    h1 = branch(base, 'p1', [change('update', letter(base), 'Лист у кишені', 'p1', category='open_threads', characters=())])
    h2 = branch(base, 'p2', [change('update', letter(base), 'Лист спалено', 'p2', category='open_threads', characters=())])
    plan = plan_merge({'h1': h1, 'h2': h2}, ORDER)
    journal = build_merged_journal(plan, {plan.conflicts[0].key: {'choice': 'author', 'text': ''}}, SOURCES, 'p2')
    assert letter(base).claim_id not in replay_memory(journal)


def test_missing_decision_names_the_key():
    base = base_journal()
    h1 = branch(base, 'p1', [change('update', coat(base), 'Анна в куртці', 'p1', slot='clothing')])
    h2 = branch(base, 'p2', [change('update', coat(base), 'Анна в плащі', 'p2', slot='clothing')])
    with pytest.raises(ValueError, match='slot:c1:clothing'):
        build_merged_journal(plan_merge({'h1': h1, 'h2': h2}, ORDER), {}, SOURCES, 'p2')


def test_events_are_ordered_by_source_position():
    base = base_journal()
    h1 = branch(branch(base, 'p1', [add('facts', 'Перше', 'p1')]), 'p3', [add('facts', 'Третє', 'p3')])
    h2 = branch(base, 'p2', [add('facts', 'Друге', 'p2')])
    journal = build_merged_journal(plan_merge({'h1': h1, 'h2': h2}, ORDER), {}, ['p0', 'p1', 'p2', 'p3'], 'p3')
    assert [e.text for e in journal.events[3:]] == ['Перше', 'Друге', 'Третє']


def test_diverging_prefix_is_rejected():
    base = base_journal()
    other = _extend(MemoryJournal(), 'p0', [add('facts', 'Інша історія', 'p0')])
    with pytest.raises(ValueError, match='h2'):
        shared_base({'h1': branch(base, 'p1', []), 'h2': branch(other, 'p2', [])}, ORDER)


def test_decisions_carry_only_for_same_values():
    old = [{'key': 'slot:c1:clothing', 'values': {'h1': 'Анна в куртці', 'h2': 'Анна в плащі'}}]
    decisions = {'slot:c1:clothing': {'choice': 'h2'}}
    same = Conflict('slot:c1:clothing', {'h1': 'Анна в куртці', 'h2': 'Анна в плащі'}, {})
    changed = Conflict('slot:c1:clothing', {'h1': 'Анна в куртці', 'h2': 'Анна в шубі'}, {})
    assert carry_decisions(old, decisions, [same]) == decisions
    assert carry_decisions(old, decisions, [changed]) == {}
