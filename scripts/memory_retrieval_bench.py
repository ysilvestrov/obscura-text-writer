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

from memory_bench.extract import extract_story  # noqa: E402
from memory_bench.metrics import aggregate, control_hits, pair_hits, pair_summary, scene_metrics  # noqa: E402
from memory_bench.model import DEFAULT_TOKENIZER, FERTILITY, realistic_ratio, set_tokenizer  # noqa: E402
from memory_bench.ranking import pair_ranks  # noqa: E402
from memory_bench.strategies import (STRATEGIES, Params, catalog_full, catalog_full_v4, catalog_narrow,  # noqa: E402
                                     catalog_narrow_v4, fts_rank, full, product, record_layers)
from memory_bench.synthetic import fit_linear, generate, measure_rates  # noqa: E402

MEASURES = ('conservative', 'realistic')
CORE_AWARE = ('structural', 'structural_fts')
VECTOR_PREFIXES = ('structural_vec[', 'structural_hybrid[')
CLOUD_KEYS = ('azure-3-large',)  # models that go to the network; checked before embeddings.py (numpy) is imported
CLOUD_ENV = ('AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'AZURE_OPENAI_API_VERSION')
DEFAULT_CACHE_DIR = r'C:\tmp\rag-bench\cache'
CLOUD_PRICE_PER_MTOK = 0.13  # USD list price for text-embedding-3-large, per million tokens
SAMPLES_PER_SYNTHETIC = 60


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
    from memory_bench.embeddings import AzureEmbedder, LocalEmbedder
    if spec['kind'] == 'cloud':
        env = os.environ
        return AzureEmbedder(key, env['AZURE_OPENAI_ENDPOINT'], env['AZURE_OPENAI_API_KEY'],
                             env['AZURE_OPENAI_EMBEDDING_DEPLOYMENT'], env['AZURE_OPENAI_API_VERSION'],
                             args.cloud_price_per_mtok, args.cloud_max_usd, model_id=spec['model_id'],
                             revision=spec['revision'])
    return LocalEmbedder(key, spec['model_id'], spec['revision'], spec['query_prefix'], spec['passage_prefix'],
                         spec['max_tokens'], threads=1)


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
        if not all(os.environ.get(name) for name in CLOUD_ENV):
            return None, 'cloud_config_missing'
    if _inside_repo(args.cache_dir):
        return None, 'inside_repo'
    models = []
    try:
        for key in keys:
            began = time.perf_counter()
            inner = make_inner_embedder(key, MODELS[key], args)
            timed, cached = _wrap(key, inner, args.cache_dir, time.perf_counter() - began)
            models.append({'key': key, 'spec': MODELS[key], 'inner': inner, 'timed': timed, 'cached': cached})
    except ImportError:
        close_vectors(models)
        return None, 'vector_deps_missing'
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
    libs = _lib_versions()
    out = {}
    for model in models:
        inner, timed, cached, spec = model['inner'], model['timed'], model['cached'], model['spec']
        local = spec['kind'] == 'local'
        entry = {'model_id': inner.model_id, 'revision': inner.revision, 'dim': int(cached.dim),
                 'max_tokens': inner.max_tokens, 'query_prefix': getattr(inner, 'query_prefix', ''),
                 'passage_prefix': getattr(inner, 'passage_prefix', ''), 'truncated': cached.truncated,
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
    directory and a new inner embedder, at the largest context (realistic measure). Local models only."""
    from memory_bench.strategies import vector_strategies
    main = vector_strategies(model['cached'])
    began = time.perf_counter()
    inner = make_inner_embedder(model['key'], model['spec'], args)
    with tempfile.TemporaryDirectory(prefix='rag-bench-repro-') as tmp:
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


def run(args):
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
    models = None
    if args.vector_models:
        models, error = setup_vectors(args, story.id)
        if error:
            return None, error
    try:
        return _build_report(args, repo, story, models), None
    finally:
        close_vectors(models or [])


def _build_report(args, repo, story, models):
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
        rankers = {}
        for model in models or []:
            from memory_bench.ranking import rrf_rank, vec_rank
            embedder, key = model['cached'], model['key']
            rankers[f'vec[{key}]'] = lambda pool, query, e=embedder: vec_rank(pool, query, e)
            rankers[f'hybrid[{key}]'] = lambda pool, query, e=embedder: rrf_rank(pool, query, e)
        report['pairs'], report['ranking'] = evaluate_pairs(scenes, others, args, contexts, pair_data, rankers, extra)
    if args.budget_steps:
        report['budget_steps'] = evaluate_budget_steps(scenes, args, pair_data, extra)
    if models:
        repro = {}
        if args.repro:
            repro = {m['key']: repro_share(m, scenes, others, args, biggest) for m in models if m['spec']['kind'] == 'local'}
        report['vector'] = vector_report(models, args, repro)
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
    parser.add_argument('--budget-steps', help='comma-separated shares of the full memory as budget, e.g. 1.0,0.75,0.5,0.35,0.25')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--tokenizer', choices=sorted(FERTILITY), default=DEFAULT_TOKENIZER,
                        help='realistic measure: Ukrainian fertility of this tokenizer family (ukrqualbench)')
    parser.add_argument('--vector-models', help='comma-separated keys of embedding models, e.g. e5-base,bge-m3,azure-3-large')
    parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help='vector cache; must be outside the repository')
    parser.add_argument('--cloud', action='store_true', help='allow the cloud model (azure-3-large) for stories of --cloud-stories')
    parser.add_argument('--cloud-stories', default='', help='comma-separated story ID prefixes that may be sent to the cloud')
    parser.add_argument('--cloud-max-usd', type=float, default=2.0, help='estimate above this stops the run')
    parser.add_argument('--cloud-price-per-mtok', type=float, default=CLOUD_PRICE_PER_MTOK)
    parser.add_argument('--repro', action='store_true', help='re-run the local vector variants on an empty cache in a temporary directory')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    set_tokenizer(args.tokenizer)
    try:
        report, error = run(args)
    except ValueError as exc:  # cloud_budget, cloud_http_<status>, cloud_error, cloud_bad_response: codes only
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
