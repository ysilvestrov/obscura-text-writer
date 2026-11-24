from memory_bench.metrics import pair_hits, pair_summary
from memory_bench.model import Selection
from tests.retrieval_bench.helpers import rec, scene

PAIRS = {'pairs': [{'id': 'P01', 'repeat': 11}, {'id': 'P02', 'repeat': 12}], 'controls': [{'id': 'C01', 'repeat': 11}]}


def sel(ids, retrieval=()):
    return Selection('s', tuple(ids), {}, 0, 0, 0, False, 0, retrieval_ids=tuple(retrieval))


def scenes(*numbers, records=()):
    return {n: scene(records, number=n) for n in numbers}


def rows_by_id(rows):
    return {r['id']: r for r in rows}


def test_pair_hit_and_by_retrieval():
    records = [rec('a', 'facts', 'x'), rec('b', 'facts', 'y'), rec('c', 'facts', 'z')]
    annotation = {'P01': ['a'], 'P02': ['b'], 'C01': ['c']}
    sels = {11: sel(['a', 'c'], ['a']), 12: sel(['b'], [])}
    out = rows_by_id(pair_hits(annotation, PAIRS, scenes(11, 12, records=records), sels))
    assert out['P01'] == {'id': 'P01', 'kind': 'pair', 'hit': True, 'by_retrieval': True, 'reason': None}
    assert out['P02']['hit'] is True and out['P02']['by_retrieval'] is False
    assert out['C01']['kind'] == 'control' and out['C01']['hit'] is True and out['C01']['by_retrieval'] is False


def test_pair_miss_is_false_not_none():
    records = [rec('a', 'facts', 'x')]
    out = rows_by_id(pair_hits({'P01': ['a']}, PAIRS, scenes(11, records=records), {11: sel([])}))
    assert out['P01']['hit'] is False and out['P01']['by_retrieval'] is False and out['P01']['reason'] is None


def test_pair_missing_in_memory():
    out = rows_by_id(pair_hits({'P01': ['gone']}, PAIRS, scenes(11, records=[rec('a', 'facts', 'x')]), {11: sel(['a'], ['a'])}))
    assert out['P01'] == {'id': 'P01', 'kind': 'pair', 'hit': None, 'by_retrieval': None, 'reason': 'missing_in_memory'}


def test_pair_scene_skipped():
    out = rows_by_id(pair_hits({'P01': ['a']}, PAIRS, {}, {}))
    assert out['P01']['reason'] == 'scene_skipped' and out['P01']['hit'] is None
    out = rows_by_id(pair_hits({'P01': ['a']}, PAIRS, scenes(11, records=[rec('a', 'facts', 'x')]), {}))
    assert out['P01']['reason'] == 'scene_skipped'


def test_pair_not_annotated():
    out = rows_by_id(pair_hits({'P01': []}, PAIRS, scenes(11, 12), {11: sel([]), 12: sel([])}))
    assert out['P01']['reason'] == 'not_annotated' and out['P02']['reason'] == 'not_annotated'
    assert out['C01']['reason'] == 'not_annotated'


def test_pair_summary_excludes_reasons_from_total():
    rows = [{'id': 'P01', 'kind': 'pair', 'hit': True, 'by_retrieval': True, 'reason': None},
            {'id': 'P02', 'kind': 'pair', 'hit': False, 'by_retrieval': False, 'reason': None},
            {'id': 'P03', 'kind': 'pair', 'hit': None, 'by_retrieval': None, 'reason': 'missing_in_memory'},
            {'id': 'C01', 'kind': 'control', 'hit': True, 'by_retrieval': False, 'reason': None},
            {'id': 'C02', 'kind': 'control', 'hit': None, 'by_retrieval': None, 'reason': 'scene_skipped'}]
    assert pair_summary(rows) == {'pair': {'hit': 1, 'by_retrieval': 1, 'total': 2},
                                  'control': {'hit': 1, 'by_retrieval': 0, 'total': 1}}


def test_pair_rows_contain_no_claim_ids():
    records = [rec('secret_claim', 'facts', 'x')]
    rows = pair_hits({'P01': ['secret_claim']}, PAIRS, scenes(11, records=records), {11: sel(['secret_claim'], ['secret_claim'])})
    assert 'secret_claim' not in repr(rows)
    assert all(set(r) == {'id', 'kind', 'hit', 'by_retrieval', 'reason'} for r in rows)
