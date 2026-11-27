import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from memory_bench.paraphrase import (LEVELS, Query, check_owner_file, content_words, in_plan_scene, level_ok, manifest, owner_sample,
                                     sample_targets, sampling_frame, set_verdict, share_stem, shared_stems,
                                     snapshot_hash, write_owner_file)
from memory_bench.strategies import Params, record_layers
from tests.retrieval_bench.helpers import NAMES, rec, rich_records, scene

P = Params(memory_budget_tokens=100000, measure='conservative', core_mode='upper')


@pytest.mark.parametrize('a,b,expected', [('дах', 'даху', True), ('тече', 'течу', True),
    ('кросівки', 'кросівок', True), ('кросівки', 'кров', True), ('маяк', 'мак', False)])
def test_share_stem(a, b, expected): assert share_stem(a, b) is expected


def test_names_are_not_shared_stems():
    assert shared_stems('Марія знову там', 'Марія шукає ключ', NAMES.values()) == 0


def test_level_ok():
    rec_text = 'Ключ від ліхтарної кімнати лежить у бляшанці'
    assert level_ok('same', 'Знову ключ у бляшанці', rec_text, [])
    assert not level_ok('syn', 'Знову ключі в бляшанках', rec_text, [])
    assert level_ok('desc', 'Металева коробка з-під заварки ховає те, чим відмикають верх', rec_text, [])


def test_sampling_frame_excludes_layers_and_timeline():
    recs = rich_records() + [rec('tl1', 'timeline', 'Подія з хронології', scene=3)]
    s1 = scene(recs)
    s2 = scene(recs, id='s11', number=11)
    layers = record_layers(s1, P)
    assert layers
    frame = sampling_frame([s1, s2], P)
    ids = [r.claim_id for r in frame]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    assert not set(ids) & set(layers) and 'tl1' not in ids
    assert 'fact_far' in ids and 'thr_far' in ids


def _frame(n=40):
    out = []
    for i in range(n):
        cat = ('facts', 'open_threads', 'character_states')[i % 3]
        out.append(rec(f'r{i:02d}', cat, f'Запис {i}', scene=1 + i % 10))
    return out


def test_sample_targets_deterministic_and_stratified():
    frame = _frame()
    a = sample_targets(frame, 10, 12, 7)
    b = sample_targets(list(reversed(frame)), 10, 12, 7)
    assert [r.claim_id for r in a] == [r.claim_id for r in b] == sorted(r.claim_id for r in a)
    assert len(a) == 12
    strata = {(r.category, min(2, (r.source_scene - 1) * 3 // 10)) for r in frame}
    got = {(r.category, min(2, (r.source_scene - 1) * 3 // 10)) for r in a}
    assert len(strata) <= 12 and got == strata
    assert [r.claim_id for r in sample_targets(frame, 10, 12, 8)] != [r.claim_id for r in a]
    assert [r.claim_id for r in sample_targets(frame, 10, 100, 7)] == sorted(r.claim_id for r in frame)


def test_in_plan_scene_first_later_scene_or_none():
    r = rec('x1', 'facts', 'Запис про дах', scene=4)
    other = rec('x2', 'facts', 'Інше')
    s5 = scene([r, other], id='s5', number=5)
    s7 = scene([r], id='s7', number=7)
    s3 = scene([r], id='s3', number=3)
    s4 = scene([r], id='s4', number=4)
    assert in_plan_scene(r, [s7, s3, s4, s5], P).scene_id == 's5'
    assert in_plan_scene(r, [s3, s4], P) is None
    tl = rec('tl2', 'timeline', 'Подія', scene=1)
    assert in_plan_scene(tl, [scene([tl], id='s2', number=2)], P) is None
    s6 = scene([other], id='s6', number=6)
    assert in_plan_scene(r, [s6], P) is None


def test_manifest_has_no_texts_and_snapshot_changes_with_text():
    q = [Query('r1', 'syn', 'текст запиту', 'ok')]
    m = manifest(q, {'seed': 0})
    assert 'текст' not in json.dumps(m, ensure_ascii=False)
    assert snapshot_hash(m) != snapshot_hash(manifest([Query('r1', 'syn', 'інший', 'ok')], {'seed': 0}))


def test_manifest_sorted_by_claim_then_level():
    qs = [Query('b', 'same', 'x', 'ok'), Query('a', 'desc', 'y', 'ok'), Query('a', 'same', 'z', 'ok')]
    m = manifest(qs, {})
    assert [(x['claim_id'], x['level']) for x in m['queries']] == [('a', 'same'), ('a', 'desc'), ('b', 'same')]


CATS = ('character_states', 'facts', 'open_threads')


def _cells_queries(n=12, status=lambda i: 'ok'):
    """n records (categories rotate), three levels each."""
    cats = {f'r{i:02d}': CATS[i % 3] for i in range(n)}
    qs = [Query(c, level, f'запит {c} {level}', status(i), 'h') for i, c in enumerate(cats) for level in LEVELS]
    return qs, cats


def test_owner_sample_ok_only_round_robin_deterministic():
    qs, cats = _cells_queries(status=lambda i: 'ok' if i % 5 else 'rejected')
    s = owner_sample(qs, 9, 1, cats)
    assert all(q.status == 'ok' for q in s) and len(s) == 9
    assert s == owner_sample(qs, 9, 1, cats)
    assert s != owner_sample(qs, 9, 2, cats)  # the seed decides which record of a cell is taken


def test_owner_sample_covers_every_level_category_cell():
    qs, cats = _cells_queries()
    s = owner_sample(qs, 20, 0, cats)
    cells = {(q.level, cats[q.claim_id]) for q in s}
    assert len(s) == 20 and cells == {(lv, c) for lv in LEVELS for c in CATS}  # 9 cells, all present
    counts = [sum(1 for q in s if (q.level, cats[q.claim_id]) == cell) for cell in cells]
    assert max(counts) - min(counts) <= 1  # one from each cell first, then round-robin
    assert len({(q.claim_id, q.level) for q in s}) == 20
    # an empty cell is skipped; a level with a single category still gets its share
    only = [q for q in qs if not (q.level == 'desc' and cats[q.claim_id] != 'facts')]
    s = owner_sample(only, 9, 0, cats)
    assert {(q.level, cats[q.claim_id]) for q in s} == {(lv, c) for lv in ('same', 'syn') for c in CATS} | {('desc', 'facts')}


def _owner(outside_dir, k=20):
    qs = [Query(f'r{i:02d}', LEVELS[i % 3], f'запит {i}', 'ok', 'h') for i in range(30)]
    snap = snapshot_hash(manifest(qs, {'seed': 0}))
    sample = owner_sample(qs, k, 0, {q.claim_id: CATS[int(q.claim_id[1:]) % 2] for q in qs})
    path = outside_dir / 'owner.json'
    write_owner_file(path, sample, snap, {q.claim_id: f'запис {q.claim_id}' for q in sample})
    return qs, snap, path


def test_owner_file_codes(outside_dir):
    qs, snap, path = _owner(outside_dir)
    assert check_owner_file(outside_dir / 'none.json', qs, snap)[0] == 'owner_check_missing'
    assert check_owner_file(path, qs, snap) == ('owner_check_missing', {'yes': 0, 'no': 0, 'invalid': 20})
    for i in range(20):
        set_verdict(path, i, 'yes')
    assert check_owner_file(path, qs, snap) == (None, {'yes': 20, 'no': 0, 'invalid': 0})
    assert check_owner_file(path, qs, 'other')[0] == 'owner_check_stale'
    changed = [Query(q.claim_id, q.level, q.text + '!' if q.claim_id == 'r00' else q.text, q.status, q.record_sha256)
               for q in qs]
    assert check_owner_file(path, changed, snap)[0] == 'owner_check_stale'
    assert check_owner_file(path, [q for q in qs if q.claim_id != 'r00'], snap)[0] == 'owner_check_stale'
    for i in range(4):
        set_verdict(path, i, 'no')
    assert check_owner_file(path, qs, snap) == (None, {'yes': 16, 'no': 4, 'invalid': 0})
    set_verdict(path, 4, 'no')
    assert check_owner_file(path, qs, snap) == ('owner_check_failed', {'yes': 15, 'no': 5, 'invalid': 0})


def test_owner_file_invalid_verdict_text(outside_dir):
    qs, snap, path = _owner(outside_dir)
    data = json.loads(path.read_text(encoding='utf-8'))
    for it in data['items']:
        it['verdict'] = ' YES '
    data['items'][0]['verdict'] = 'Так'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    assert check_owner_file(path, qs, snap) == ('owner_check_missing', {'yes': 19, 'no': 0, 'invalid': 1})


def test_set_verdict_values_and_summary(outside_dir):
    qs, snap, path = _owner(outside_dir)
    assert set_verdict(path, 0, ' Yes ') == {'yes': 1, 'no': 0, 'pending': 19, 'failed': False}
    assert json.loads(path.read_text(encoding='utf-8'))['items'][0]['verdict'] == 'yes'
    assert set_verdict(path, 0, None)['pending'] == 20
    for bad in ('maybe', 'Так'):
        with pytest.raises(ValueError, match='bad_verdict'):
            set_verdict(path, 0, bad)
    with pytest.raises(ValueError, match='bad_verdict'):
        set_verdict(path, 20, 'yes')
    assert not list(path.parent.glob('*.tmp'))
    for i in range(5):
        res = set_verdict(path, i, 'no')
    assert res['failed'] is True


def test_owner_file_refuses_inside_repo():
    inside = Path(__file__).resolve().parent / 'owner_inside.json'
    with pytest.raises(ValueError, match='inside_repo'):
        write_owner_file(inside, [], 'snap', {})
    assert not inside.exists()
    inside.write_text('{"snapshot":"s","items":[{"verdict":null}]}', encoding='utf-8')
    try:
        with pytest.raises(ValueError, match='inside_repo'):
            set_verdict(inside, 0, 'yes')
    finally:
        inside.unlink()


def test_module_imports_without_numpy_and_anthropic():
    code = "import sys; sys.modules['numpy']=None; sys.modules['anthropic']=None; import memory_bench.paraphrase"
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(root / 'scripts'), str(root / 'src')])}
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=root, env=env)
    assert r.returncode == 0, r.stderr


def test_name_filter_is_prefix_of_full_stem_only():
    names = list(NAMES.values())
    assert shared_stems('Марафон на узбережжі', 'Марафон біля річки', names) == 1
    assert 'марафон' in content_words('Марафон', names)
    assert content_words('Марії Марією Остапа Ганні', names) == []
    assert not level_ok('same', 'Марія й Остап шукають', 'Марії та Остапом щось', names)


def _items(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _put(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def test_owner_file_item_without_identity_is_stale(outside_dir):
    qs, snap, path = _owner(outside_dir)
    for i in range(20):
        set_verdict(path, i, 'yes')
    data = _items(path)
    del data['items'][0]['sha256']
    _put(path, data)
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_stale'
    data = _items(path)
    data['items'][0]['sha256'] = 'x'
    data['items'][0]['claim_id'] = 'unknown'
    _put(path, data)
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_stale'
    _put(path, {'snapshot': snap, 'items': [{'verdict': 'yes'}] * 20})
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_stale'


def test_owner_file_count_and_duplicates(outside_dir):
    qs, snap, path = _owner(outside_dir)
    for i in range(20):
        set_verdict(path, i, 'yes')
    full = _items(path)
    _put(path, {**full, 'items': []})
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_missing'
    _put(path, {**full, 'items': full['items'][:19]})
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_missing'
    _put(path, {**full, 'items': full['items'][:19] + [full['items'][0]]})
    assert check_owner_file(path, qs, snap)[0] == 'owner_check_missing'
    _put(path, {**full, 'items': full['items'][:19]})
    assert check_owner_file(path, qs, snap, expected=19) == (None, {'yes': 19, 'no': 0, 'invalid': 0})


def _fake_worktree(base):
    """A fake main repository and a fake worktree checkout whose .git file points at <main>/.git/worktrees/w."""
    main, checkout = base / 'mainrepo', base / 'wt'
    (main / '.git' / 'worktrees' / 'w').mkdir(parents=True)
    checkout.mkdir()
    (checkout / '.git').write_text(f"gitdir: {main / '.git' / 'worktrees' / 'w'}\n", encoding='utf-8')
    return main, checkout


def test_inside_repo_covers_main_checkout_of_a_worktree(tmp_path, monkeypatch):
    import memory_bench.paraphrase as para
    main, checkout = _fake_worktree(tmp_path)
    monkeypatch.setattr(para, 'ROOT', checkout)
    assert para._inside_repo(checkout / 'x.json')
    assert para._inside_repo(main / 'data' / 'owner.json')  # the main checkout is protected from a worktree too
    assert not para._inside_repo(tmp_path / 'elsewhere')
    (checkout / '.git').unlink()
    (checkout / '.git').mkdir()  # an ordinary checkout: only its own root
    assert not para._inside_repo(main / 'data')


def test_embeddings_uses_the_same_inside_repo(tmp_path, monkeypatch):
    pytest.importorskip('numpy')
    import memory_bench.embeddings as emb
    import memory_bench.paraphrase as para
    assert emb._inside_repo is para._inside_repo
    main, checkout = _fake_worktree(tmp_path)
    monkeypatch.setattr(para, 'ROOT', checkout)
    with pytest.raises(ValueError, match='inside_repo'):
        emb.CachedEmbedder(emb.FakeEmbedder(), main / 'cache')


def test_owner_file_items_outside_the_expected_sample_are_stale(outside_dir):
    qs, snap, path = _owner(outside_dir)
    for i in range(20):
        set_verdict(path, i, 'yes')
    sample = {(i['claim_id'], i['level']) for i in _items(path)['items']}
    assert check_owner_file(path, qs, snap, sample_keys=sample) == (None, {'yes': 20, 'no': 0, 'invalid': 0})
    other = set(list(sample)[1:]) | {next((q.claim_id, q.level) for q in qs if (q.claim_id, q.level) not in sample)}
    assert check_owner_file(path, qs, snap, sample_keys=other)[0] == 'owner_check_stale'
