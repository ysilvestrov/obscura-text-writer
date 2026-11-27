"""Read-only memory retrieval bench (#25): compares memory selection strategies on a COPY of the data directory.

Prints aggregates, codes and the protagonist ID only: never story texts, character names or claim IDs."""
import argparse
import json
import math
import os
import statistics
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.cloud_spend import BudgetExceeded, LedgerMissing, SpendLedger, read_env_key  # noqa: E402
from memory_bench.extract import extract_story  # noqa: E402
from memory_bench.metrics import aggregate, control_hits, pair_hits, pair_summary, scene_metrics  # noqa: E402
from memory_bench.model import DEFAULT_TOKENIZER, FERTILITY, realistic_ratio, set_tokenizer  # noqa: E402
from memory_bench.paraphrase_eval import evaluate_paraphrases, frame_by_id, stale_queries  # noqa: E402
from memory_bench.ranking import pair_ranks  # noqa: E402
from memory_bench.strategies import (STRATEGIES, Params, catalog_full, catalog_full_v4, catalog_narrow,  # noqa: E402
                                     catalog_narrow_v4, fts_rank, full, product, record_layers)
from memory_bench.synthetic import fit_linear, generate, measure_rates  # noqa: E402

MEASURES = ('conservative', 'realistic')
CORE_AWARE = ('structural', 'structural_fts')
VECTOR_PREFIXES = ('structural_vec[', 'structural_hybrid[')
CLOUD_KEYS = ('voyage-4',)  # models that go to the network; checked before embeddings.py (numpy) is imported
CLOUD_KEY_ENV = 'ATLAS_EMBEDDING_API_KEY'
DEFAULT_CACHE_DIR = r'C:\tmp\rag-bench\cache'
DEFAULT_SPEND_LEDGER = r'C:\tmp\rag-bench\spend.json'  # cumulative, shared with the paraphrase/context generators
DEFAULT_ENV_FILE = r'C:\Projects\text-generator\.env'
SAMPLES_PER_SYNTHETIC = 60
from memory_bench.paraphrase import OWNER_K  # noqa: E402  (meta['owner_k'] must equal it; absent means it)


def variants(extra=None):
    """(key, strategy name, core mode); extra holds the vector strategies of --vector-models, after the built-in ones."""
    for name in [*STRATEGIES, *(extra or {})]:
        if name in CORE_AWARE or name.startswith(VECTOR_PREFIXES):
            for mode in ('upper', 'lower'):
                yield f'{name}[core={mode}]', name, mode
        else:
            yield name, name, 'upper'


def _ints(text):
    return [int(x) for x in text.split(',') if x.strip()]


def other_context(repo, story_id, scene_id):
    """Non-memory part of the scene's last draft request from its stored breakdown: (conservative, realistic) tokens."""
    for attempt in reversed(repo.list_attempts(story_id, scene_id=scene_id)):
        breakdown = attempt.context.get('context_breakdown') if attempt.stage == 'draft' else None
        if breakdown and breakdown.get('parts'):
            parts = [p for p in breakdown['parts'] if p.get('kind') != 'memory']
            conservative = sum(p.get('request_bytes') or 0 for p in parts) + 256
            realistic = sum(p['characters'] if p.get('characters') is not None else p.get('request_bytes') or 0
                            for p in parts) / realistic_ratio()
            return {'conservative': conservative, 'realistic': int(realistic)}
    return None


def budget(context, args, other, measure):
    room = context - args.output_reserve
    if args.other_context != 'auto':
        return max(0, room - int(args.other_context))
    if other is None:
        return max(0, int(args.memory_share * room))
    return max(0, room - other[measure])


def evaluate(scenes, others, args, contexts, measures, extra=None):
    strategies = {**STRATEGIES, **(extra or {})}
    result = {}
    for context in contexts:
        result[str(context)] = {}
        for measure in measures:
            result[str(context)][measure] = {}
            for key, name, mode in variants(extra):
                rows, sels = [], []
                for scene in scenes:
                    params = Params(budget(context, args, others.get(scene.scene_id), measure), measure, mode,
                                    core_recent_scenes=args.core_recent)
                    sel = strategies[name](scene, params)
                    rows.append(scene_metrics(scene, sel))
                    sels.append(sel)
                result[str(context)][measure][key] = aggregate(rows, sels)
    return result


def evaluate_product(scenes, others, args, contexts):
    """The product's selection (#60) on real scenes only; kept apart from 'real' so existing keys stay unchanged."""
    result = {}
    for context in contexts:
        result[str(context)] = {}
        for measure in MEASURES:
            sels = [product(s, Params(budget(context, args, others.get(s.scene_id), measure), measure, 'upper')) for s in scenes]
            result[str(context)][measure] = aggregate([scene_metrics(s, x) for s, x in zip(scenes, sels)], sels)
    return result


def memory_stage_v4(scenes):
    """Full and narrowed memory-stage catalog v4 on real scenes (#60); kept apart from the v3 'memory_stage'."""
    out = {}
    for label, build in (('full', catalog_full_v4), ('narrow', catalog_narrow_v4)):
        sels = [build(s) for s in scenes]
        out[label] = aggregate([scene_metrics(s, x) for s, x in zip(scenes, sels)], sels)
    return out


def growth(scenes, args):
    if len({s.number for s in scenes}) < 2:
        return {}
    out = {}
    for key, name, mode in variants():
        points = []
        for scene in scenes:
            # Unbounded budget: growth measures what each strategy selects, not what one context can hold.
            params = Params(10 ** 12, 'conservative', mode, core_recent_scenes=args.core_recent)
            points.append((scene.number, STRATEGIES[name](scene, params).chars))
        slope, intercept = fit_linear(points)
        out[key] = {'slope_chars': round(slope, 1), 'intercept_chars': round(intercept, 1),
                    'projected': {str(n): round(slope * n + intercept) for n in (300, 3000)}}
    return out


def _selections(scenes, name, mode, args, budget_of, measure, extra=None):
    strategies = {**STRATEGIES, **(extra or {})}
    return {s.number: strategies[name](s, Params(budget_of(s), measure, mode, core_recent_scenes=args.core_recent))
            for s in scenes}


def _load_pairs(args, story_id):
    """(pairs, annotation of this story) when both files are given, else None."""
    if not (args.pairs and args.pairs_annotation):
        return None
    pairs = json.loads(Path(args.pairs).read_text(encoding='utf-8'))
    stories = json.loads(Path(args.pairs_annotation).read_text(encoding='utf-8')).get('stories', {})
    return pairs, stories.get(story_id) or {}


def evaluate_budget_steps(scenes, args, pair_data, extra=None):
    """Memory budget of a scene = step x the realistic tokens of its full memory; pairs only with pair data."""
    unbounded = Params(10 ** 12, 'realistic', 'upper')
    totals = {s.scene_id: full(s, unbounded).tokens_realistic for s in scenes}
    by_number = {s.number: s for s in scenes}
    result = {}
    for text in args.budget_steps.split(','):
        step, result[text.strip()] = float(text), {}
        for key, name, mode in variants(extra):
            sels = _selections(scenes, name, mode, args, lambda s: int(step * totals[s.scene_id]), 'realistic', extra)
            ordered = [sels[s.number] for s in scenes]
            entry = aggregate([scene_metrics(s, x) for s, x in zip(scenes, ordered)], ordered)
            if pair_data:
                entry['pairs'] = pair_summary(pair_hits(pair_data[1], pair_data[0], by_number, sels))
            result[text.strip()][key] = entry
    return result


def retrieval_layer(name):
    """Layer label of a strategy's retrieval_ids: 'fts', 'vec' or 'hybrid'; None for strategies without retrieval."""
    if name == 'structural_fts':
        return 'fts'
    if name.startswith('structural_vec['):
        return 'vec'
    return 'hybrid' if name.startswith('structural_hybrid[') else None


def layer_counts(annotation, entries, scenes_by_number, selections, params, retrieval='fts'):
    """Where annotated records present in memory came from: retrieval (fts / vec / hybrid), a structural layer or not
    selected."""
    counts = {'not_selected': 0}
    for entry in entries:
        scene, sel = scenes_by_number.get(entry['repeat']), selections.get(entry['repeat'])
        if scene is None or sel is None:
            continue
        by_layer, retrieved, chosen = record_layers(scene, params), set(sel.retrieval_ids), set(sel.record_ids)
        categories = {r.claim_id: r.category for r in scene.records}
        for claim in set(annotation.get(entry['id']) or ()) & set(categories):
            if claim not in chosen:
                layer = 'not_selected'
            elif claim in retrieved:
                layer = retrieval
            else:
                layer = by_layer.get(claim) or ('timeline' if categories[claim] == 'timeline' else 'other')
            counts[layer] = counts.get(layer, 0) + 1
    return counts


def evaluate_pairs(scenes, others, args, contexts, pair_data, rankers=None, extra=None):
    """pairs / ranking sections at the largest context (realistic measure); counts and codes only."""
    pairs, annotation = pair_data
    by_number = {s.number: s for s in scenes}
    biggest = max(contexts)
    budget_of = lambda s: budget(biggest, args, others.get(s.scene_id), 'realistic')
    summary, layers, layers_control = {}, {}, {}
    for key, name, mode in variants(extra):
        sels = _selections(scenes, name, mode, args, budget_of, 'realistic', extra)
        summary[key] = pair_summary(pair_hits(annotation, pairs, by_number, sels))
        label = retrieval_layer(name)
        if label:
            params = Params(0, 'realistic', mode, core_recent_scenes=args.core_recent)
            layers[key] = layer_counts(annotation, pairs.get('pairs', []), by_number, sels, params, label)
            layers_control[key] = layer_counts(annotation, pairs.get('controls', []), by_number, sels, params, label)
    ranking = pair_ranks({'bm25': fts_rank, **(rankers or {})}, annotation, pairs, by_number)
    return summary, {**ranking, 'layers': layers, 'layers_control': layers_control}


class TimedEmbedder:
    """Times the inner embed calls (cache hits never reach it); everything else is delegated to the inner embedder."""

    def __init__(self, inner, load_seconds=0.0):
        self.inner, self.load_seconds, self.calls = inner, load_seconds, []

    def __getattr__(self, name):
        if name == 'inner':
            raise AttributeError(name)
        return getattr(self.inner, name)

    def embed(self, texts, kind):
        began = time.perf_counter()
        try:
            return self.inner.embed(texts, kind)
        finally:
            self.calls.append(time.perf_counter() - began)

    @property
    def cold_seconds(self):
        """Model load plus the first embed call; None when every text came from the cache."""
        return self.load_seconds + self.calls[0] if self.calls else None

    @property
    def total_seconds(self):
        return self.load_seconds + sum(self.calls)


def make_inner_embedder(key, spec, args):
    """The only place a real model or the cloud client is built; tests replace it. Missing libraries raise ImportError."""
    from memory_bench.embeddings import LocalEmbedder, VoyageEmbedder
    if spec['kind'] == 'cloud':
        ledger = SpendLedger.open(Path(args.spend_ledger), _cloud_caps(args))  # never created here
        return VoyageEmbedder(key, read_env_key(CLOUD_KEY_ENV, args.env_file), ledger, model_id=spec['model_id'],
                              revision=spec['revision'], dim=spec['dim'])
    return LocalEmbedder(key, spec['model_id'], spec['revision'], spec['query_prefix'], spec['passage_prefix'],
                         spec['max_tokens'], threads=1,
                         trust_remote_code=spec.get('trust_remote_code', False), dtype=spec.get('dtype'))


def _cloud_caps(args):
    return {'voyage': args.voyage_max_usd}


def _wrap(key, inner, cache_dir, load_seconds):
    from memory_bench.embeddings import CachedEmbedder
    timed = TimedEmbedder(inner, load_seconds)
    return timed, CachedEmbedder(timed, Path(cache_dir) / key)


def setup_vectors(args, story_id):
    """([model dicts], None) or (None, code). Every refusal happens before any embedder is built or the network used."""
    keys = list(dict.fromkeys(k.strip() for k in args.vector_models.split(',') if k.strip()))
    if any(k in CLOUD_KEYS for k in keys) and not args.cloud:
        return None, 'cloud_not_allowed'
    try:
        from memory_bench.embeddings import MODELS, _inside_repo, cloud_allowed
    except ImportError:
        return None, 'vector_deps_missing'
    if any(k not in MODELS for k in keys):
        return None, 'unknown_vector_model'
    if any(MODELS[k]['kind'] == 'cloud' for k in keys):
        if not cloud_allowed(story_id, args.cloud_stories.split(',')):
            return None, 'cloud_not_allowed'
        if not read_env_key(CLOUD_KEY_ENV, args.env_file):
            return None, 'cloud_config_missing'
        try:  # the bench never creates the ledger: an unreadable one refuses the run before any embedder exists
            SpendLedger.open(Path(args.spend_ledger), _cloud_caps(args))
        except LedgerMissing:
            return None, 'spend_ledger_missing'
    if any(MODELS[k]['kind'] == 'truncate' and MODELS[k]['base'] not in keys for k in keys):
        return None, 'truncate_base_missing'
    if _inside_repo(args.cache_dir):
        return None, 'inside_repo'
    models = []
    try:
        for key in sorted(keys, key=lambda k: MODELS[k]['kind'] == 'truncate'):  # bases before their truncations
            if MODELS[key]['kind'] == 'truncate':
                from memory_bench.embeddings import TruncatedEmbedder
                base = next(m for m in models if m['key'] == MODELS[key]['base'])
                view = TruncatedEmbedder(base['cached'], key, MODELS[key]['dim'])
                models.append({'key': key, 'spec': MODELS[key], 'inner': view, 'timed': TimedEmbedder(view), 'cached': view})
                continue
            began = time.perf_counter()
            inner = make_inner_embedder(key, MODELS[key], args)
            timed, cached = _wrap(key, inner, args.cache_dir, time.perf_counter() - began)
            models.append({'key': key, 'spec': MODELS[key], 'inner': inner, 'timed': timed, 'cached': cached})
        models.sort(key=lambda m: keys.index(m['key']))
    except ImportError:
        close_vectors(models)
        return None, 'vector_deps_missing'
    except Exception:  # e.g. OSError: model absent from the Hugging Face cache offline; never a traceback or details
        close_vectors(models)
        return None, 'vector_load_failed'
    return models, None


def close_vectors(models):
    for model in models:
        close = getattr(model['inner'], 'close', None)
        if close:
            close()


def _lib_versions():
    out = {}
    for name, dist in (('numpy', 'numpy'), ('torch', 'torch'), ('sentence_transformers', 'sentence-transformers'),
                       ('transformers', 'transformers')):
        try:
            out[name] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def _dir_bytes(path):
    """Size of the regular files under path (symlinks skipped, so Hugging Face blobs are not counted twice)."""
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            f = Path(root) / name
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
    return total


def _weights_bytes(spec):
    if spec['kind'] == 'truncate':  # same files as the base model
        from memory_bench.embeddings import MODELS
        spec = MODELS[spec['base']]
    if spec['kind'] != 'local':
        return None
    try:
        from huggingface_hub import constants
    except ImportError:
        return None
    folder = Path(constants.HF_HUB_CACHE) / ('models--' + spec['model_id'].replace('/', '--'))
    return _dir_bytes(folder) if folder.is_dir() else None


def _percentile(values, share):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def vector_report(models, args, repro):
    # load_seconds / index_seconds_cold / index_seconds cover model load plus the uncached inner embed calls of any
    # kind (passages and queries, main run only); texts answered by the cache cost nothing. Cold = load + first call.
    libs = _lib_versions()
    out = {}
    for model in models:
        inner, timed, cached, spec = model['inner'], model['timed'], model['cached'], model['spec']
        local = spec['kind'] != 'cloud'
        entry = {'model_id': inner.model_id, 'revision': inner.revision, 'dim': int(cached.dim),
                 'max_tokens': inner.max_tokens, 'query_prefix': getattr(inner, 'query_prefix', ''),
                 'passage_prefix': getattr(inner, 'passage_prefix', ''), 'truncated': cached.truncated,
                 'truncated_requests': cached.truncated_requests,
                 'threads': 1 if local else None, 'libs': libs,
                 'load_seconds': round(timed.load_seconds, 3),
                 'index_seconds_cold': None if timed.cold_seconds is None else round(timed.cold_seconds, 3),
                 'index_seconds': round(timed.total_seconds, 3), 'weights_bytes': _weights_bytes(spec),
                 'cache_bytes': _dir_bytes(cached.cache_dir), 'cache_hits': cached.hits, 'cache_misses': cached.misses,
                 'repro_identical_share': repro.get(model['key'])}
        if not local:
            lat = list(getattr(inner, 'latencies', []))
            entry.update(tokens=inner.tokens, usd=round(inner.usd, 8),
                         latency_ms={'p50': round(_percentile(lat, 0.5) * 1000, 1), 'p90': round(_percentile(lat, 0.9) * 1000, 1)}
                         if lat else {'p50': None, 'p90': None})
        out[model['key']] = entry
    return out


def repro_share(model, scenes, others, args, biggest):
    """Share of (scene, vector variant) pairs with identical record_ids after a re-run on an empty cache in a temporary
    directory and a new inner embedder, at the largest context (realistic measure). Local models always; the cloud
    model only with --repro-cloud, as one paid re-run through the spend ledger."""
    from memory_bench.strategies import vector_strategies
    main = vector_strategies(model['cached'])
    began = time.perf_counter()
    inner = make_inner_embedder(model['key'], model['spec'], args)
    with tempfile.TemporaryDirectory(prefix='rag-bench-repro-') as tmp, _closing(inner):
        _, fresh_cached = _wrap(model['key'], inner, tmp, time.perf_counter() - began)
        fresh = vector_strategies(fresh_cached)
        same = total = 0
        for name in main:
            for mode in ('upper', 'lower'):
                for scene in scenes:
                    params = Params(budget(biggest, args, others.get(scene.scene_id), 'realistic'), 'realistic', mode,
                                    core_recent_scenes=args.core_recent)
                    total += 1
                    same += main[name](scene, params).record_ids == fresh[name](scene, params).record_ids
    return same / total if total else None


class _closing:
    def __init__(self, inner):
        self.inner = inner

    def __enter__(self):
        return self.inner

    def __exit__(self, *exc):
        close = getattr(self.inner, 'close', None)
        if close:
            close()


def run(args):
    if args.repro_cloud and not args.repro:
        return None, 'repro_cloud_without_repro'
    if args.paraphrases:
        from memory_bench.paraphrase import _inside_repo
        if _inside_repo(args.paraphrases):
            return None, 'inside_repo'
    from storygen.application.workspace_bench import _check_data_dir
    try:
        data = _check_data_dir(args.data, True)
    except ValueError as error:
        return None, str(error).split(':')[0]
    try:
        from storygen.storage.repository import Repository
        repo = Repository(data)
        stories = repo.list_stories()
    except Exception:
        return None, 'db_unreadable'
    chosen = [s for s in stories if args.story is None or s.id.startswith(args.story)]
    if not chosen:
        return None, 'story_not_found'
    story = max(chosen, key=lambda s: (len(repo.list_scenes(s.id)), s.id))
    paraphrases = None
    if args.paraphrases:
        paraphrases, error = load_paraphrases(args, repo, story)
        if error:
            return None, error
    models = None
    if args.vector_models:
        models, error = setup_vectors(args, story.id)
        if error:
            return None, error
    try:
        return _build_report(args, repo, story, models, paraphrases), None
    finally:
        close_vectors(models or [])


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_paraphrases(args, repo, story):
    """(set dict, None) or (None, code). The owner's check and the freshness of the set are settled here, before any
    embedder is built: a set that fails either never reaches a model.

    Order: paraphrase_set_invalid (unreadable set, unknown level or status, owner_k other than 20, non-integer seed),
    then the owner file against owner_sample recomputed exactly as the generator calls it (owner_check_*), then
    paraphrase_set_stale (another story or protagonist, a record gone or changed, a level check that no longer holds)."""
    from memory_bench.paraphrase import (LEVELS, Query, check_owner_file, level_ok, manifest, owner_sample,
                                         snapshot_hash, story_names)
    folder = Path(args.paraphrases)
    try:
        data = json.loads((folder / 'set.json').read_text(encoding='utf-8'))
        meta = data['meta']
        queries = [Query(q['claim_id'], q['level'], q['text'], q['status'], q.get('record_sha256', ''))
                   for q in data['queries']]
        if not isinstance(meta, dict):
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        return None, 'paraphrase_set_invalid'
    if any(q.level not in LEVELS or q.status not in ('ok', 'rejected') for q in queries):
        return None, 'paraphrase_set_invalid'
    owner_k = meta.get('owner_k', OWNER_K)  # sets of the first generator version carry no owner_k: the default 20
    if not _is_int(owner_k) or owner_k != OWNER_K or not _is_int(meta.get('seed')):
        return None, 'paraphrase_set_invalid'
    snapshot = snapshot_hash(manifest(queries, meta))
    scenes, _ = extract_story(repo, story.id, args.protagonist)
    frame = frame_by_id(scenes)
    sample = owner_sample(queries, OWNER_K, meta['seed'], {k: r.category for k, r in frame.items()})
    expected = min(OWNER_K, sum(1 for q in queries if q.status == 'ok'))
    code, owner = check_owner_file(folder / 'owner-check.json', queries, snapshot, expected=expected,
                                   sample_keys={(q.claim_id, q.level) for q in sample})
    if code:
        return None, code
    protagonist = scenes[0].protagonist if scenes else None
    if meta.get('story') != story.id or meta.get('protagonist') != protagonist or stale_queries(queries, scenes):
        return None, 'paraphrase_set_stale'
    names = story_names(scenes)
    if any(not level_ok(q.level, q.text, frame[q.claim_id].text, names) for q in queries if q.status == 'ok'):
        return None, 'paraphrase_set_stale'
    return {'queries': queries, 'meta': meta, 'snapshot': snapshot, 'owner': owner, 'owner_items': expected}, None


def vector_rankers(models):
    from memory_bench.ranking import rrf_rank, vec_rank
    rankers = {}
    for model in models or []:
        embedder, key = model['cached'], model['key']
        rankers[f'vec[{key}]'] = lambda pool, query, e=embedder: vec_rank(pool, query, e)
        rankers[f'hybrid[{key}]'] = lambda pool, query, e=embedder: rrf_rank(pool, query, e)
    return rankers


def paraphrase_section(args, scenes, models, extra, paraphrases):
    """Report section 'paraphrases': ids, codes and aggregates only (no query or record text)."""
    rankers = {'bm25': fts_rank, **vector_rankers(models)}
    strategies = {'structural_fts': STRATEGIES['structural_fts'], **extra}
    params_of = lambda budget, core: Params(budget, 'realistic', core, core_recent_scenes=args.core_recent)
    keep = ('seed', 'n', 'model', 'prompt_id', 'levels')
    meta = {**{k: paraphrases['meta'].get(k) for k in keep}, 'owner_k': paraphrases['meta'].get('owner_k', OWNER_K),
            'owner_items': paraphrases['owner_items']}
    return {'meta': meta, 'snapshot': paraphrases['snapshot'],
            'owner': paraphrases['owner'],
            'levels': evaluate_paraphrases(scenes, paraphrases['queries'], rankers, strategies, params_of)}


def _build_report(args, repo, story, models, paraphrases=None):
    from memory_bench.strategies import vector_strategies
    extra = {}
    for model in models or []:
        extra.update(vector_strategies(model['cached']))
    scenes, skipped = extract_story(repo, story.id, args.protagonist)
    others = {s.scene_id: other_context(repo, story.id, s.scene_id) for s in scenes}
    contexts = _ints(args.context)
    biggest = max(contexts)
    memory_stage = {}
    for label, build in (('full', lambda s: catalog_full(s)),
                         ('narrow', lambda s: catalog_narrow(s, Params(0, 'conservative', 'upper')))):
        sels = [build(s) for s in scenes]
        memory_stage[label] = aggregate([scene_metrics(s, x) for s, x in zip(scenes, sels)], sels)
    synthetic = {}
    if scenes and _ints(args.synthetic):
        rates = measure_rates(scenes)
        known = [o for o in others.values() if o]
        median = {m: int(statistics.median(o[m] for o in known)) for m in MEASURES} if known else None
        for n in _ints(args.synthetic):
            generated = generate(rates, n, seed=args.seed, sample_every=max(1, n // SAMPLES_PER_SYNTHETIC))
            synthetic[str(n)] = evaluate(generated, {s.scene_id: median for s in generated}, args, contexts, ('conservative',))
    cases = None
    if args.control_cases:
        raw = json.loads(Path(args.control_cases).read_text(encoding='utf-8'))
        cases = {}
        by_id = {s.scene_id: s for s in scenes}
        for key, name, mode in variants():
            sels = {s.scene_id: STRATEGIES[name](s, Params(budget(biggest, args, others.get(s.scene_id), 'conservative'),
                                                           'conservative', mode, core_recent_scenes=args.core_recent))
                    for s in scenes}
            cases[key] = control_hits(raw, by_id, sels)
    pair_data = _load_pairs(args, story.id)
    report = {
        'story': {'scene_count': len(scenes),
                  'skipped': {k: v for k, v in skipped.items() if k.startswith('skipped_')},
                  'targets_unreachable': {k: v for k, v in skipped.items() if k.startswith('targets_')},
                  'protagonist_id': scenes[0].protagonist if scenes else None,
                  'first_meetings_total': sum(s.first_meetings for s in scenes),
                  'other_context_source': {'attempt': sum(1 for o in others.values() if o),
                                           'share': sum(1 for o in others.values() if not o)}},
        'real': evaluate(scenes, others, args, contexts, MEASURES, extra),
        'memory_stage': memory_stage,
        'product': evaluate_product(scenes, others, args, contexts),
        'memory_stage_v4': memory_stage_v4(scenes),
        'growth': growth(scenes, args),
        'synthetic': synthetic,
        'control_cases': cases,
        'params': {'context': contexts, 'output_reserve': args.output_reserve, 'other_context': args.other_context,
                   'memory_share': args.memory_share, 'core_recent': args.core_recent, 'seed': args.seed,
                   'tokenizer': args.tokenizer, 'chars_per_token': round(realistic_ratio(), 3), 'synthetic': _ints(args.synthetic)},
    }
    if pair_data:
        report['pairs'], report['ranking'] = evaluate_pairs(scenes, others, args, contexts, pair_data, vector_rankers(models), extra)
    if paraphrases:
        report['paraphrases'] = paraphrase_section(args, scenes, models, extra, paraphrases)
    if args.budget_steps:
        report['budget_steps'] = evaluate_budget_steps(scenes, args, pair_data, extra)
    if models:
        # Snapshot first: the re-run goes through the main embedder again and must not change its counters.
        report['vector'] = vector_report(models, args, {})
        if args.repro:
            for m in models:
                if m['spec']['kind'] == 'local' or (m['spec']['kind'] == 'cloud' and args.repro_cloud):
                    report['vector'][m['key']]['repro_identical_share'] = repro_share(m, scenes, others, args, biggest)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='copy of the data directory (the working one is refused)')
    parser.add_argument('--story', help='story ID prefix; default: the story with most scenes')
    parser.add_argument('--protagonist', help='character ID; default: most frequent in scene casts')
    parser.add_argument('--context', default='32768,65536,131072')
    parser.add_argument('--output-reserve', type=int, default=8192)
    parser.add_argument('--other-context', default='auto')
    parser.add_argument('--memory-share', type=float, default=0.25)
    parser.add_argument('--core-recent', type=int, default=3)
    parser.add_argument('--synthetic', default='300,3000')
    parser.add_argument('--control-cases')
    parser.add_argument('--pairs', help='planted pairs JSON {pairs, controls}; used together with --pairs-annotation')
    parser.add_argument('--pairs-annotation', help='annotation JSON {stories: {story_id: {pair_id: [claim_id]}}}')
    parser.add_argument('--paraphrases', help='folder with set.json and owner-check.json of scripts/rag_paraphrases.py; '
                        'must lie outside the repository; works without --vector-models (BM25 only)')
    parser.add_argument('--budget-steps', help='comma-separated shares of the full memory as budget, e.g. 1.0,0.75,0.5,0.35,0.25')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--tokenizer', choices=sorted(FERTILITY), default=DEFAULT_TOKENIZER,
                        help='realistic measure: Ukrainian fertility of this tokenizer family (ukrqualbench)')
    parser.add_argument('--vector-models', help='comma-separated keys of embedding models, e.g. e5-base,nano-2048,voyage-4')
    parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='vector cache; must be outside the repository')
    parser.add_argument('--cloud', action='store_true', help='allow the cloud model (voyage-4) for stories of --cloud-stories')
    parser.add_argument('--cloud-stories', default='', help='comma-separated story ID prefixes that may be sent to the cloud')
    parser.add_argument('--spend-ledger', default=DEFAULT_SPEND_LEDGER,
                        help='cumulative spend ledger (JSON); must exist, the bench never creates it')
    parser.add_argument('--voyage-max-usd', type=float, default=1.0,
                        help='cumulative voyage cap; a higher value than the one stored in the ledger has no effect')
    parser.add_argument('--env-file', default=DEFAULT_ENV_FILE,
                        help=f'KEY=VALUE file read for {CLOUD_KEY_ENV} when the environment lacks it')
    parser.add_argument('--repro', action='store_true', help='re-run the local vector variants on an empty cache in a temporary directory')
    parser.add_argument('--repro-cloud', action='store_true',
                        help='with --repro: also re-run the cloud model once on an empty cache (paid, through the ledger)')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    set_tokenizer(args.tokenizer)
    try:
        report, error = run(args)
    except (BudgetExceeded, LedgerMissing) as exc:  # cloud_budget_exceeded, spend_ledger_missing
        report, error = None, str(exc)
    except ValueError as exc:  # cloud_http_<status>, cloud_error, cloud_bad_response, cloud_input_type: codes only
        if not str(exc).startswith('cloud_'):
            raise
        report, error = None, str(exc)
    if error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
