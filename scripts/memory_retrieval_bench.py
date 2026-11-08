"""Read-only memory retrieval bench (#25): compares memory selection strategies on a COPY of the data directory.

Prints aggregates, codes and the protagonist ID only: never story texts, character names or claim IDs."""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.extract import extract_story  # noqa: E402
from memory_bench.metrics import aggregate, control_hits, scene_metrics  # noqa: E402
from memory_bench.model import CHARS_PER_TOKEN  # noqa: E402
from memory_bench.strategies import STRATEGIES, Params, catalog_full, catalog_narrow  # noqa: E402
from memory_bench.synthetic import fit_linear, generate, measure_rates  # noqa: E402

MEASURES = ('conservative', 'realistic')
CORE_AWARE = ('structural', 'structural_fts')
SAMPLES_PER_SYNTHETIC = 60


def variants():
    for name in STRATEGIES:
        if name in CORE_AWARE:
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
                            for p in parts) / CHARS_PER_TOKEN
            return {'conservative': conservative, 'realistic': int(realistic)}
    return None


def budget(context, args, other, measure):
    room = context - args.output_reserve
    if args.other_context != 'auto':
        return max(0, room - int(args.other_context))
    if other is None:
        return max(0, int(args.memory_share * room))
    return max(0, room - other[measure])


def evaluate(scenes, others, args, contexts, measures):
    result = {}
    for context in contexts:
        result[str(context)] = {}
        for measure in measures:
            result[str(context)][measure] = {}
            for key, name, mode in variants():
                rows, sels = [], []
                for scene in scenes:
                    params = Params(budget(context, args, others.get(scene.scene_id), measure), measure, mode,
                                    core_recent_scenes=args.core_recent)
                    sel = STRATEGIES[name](scene, params)
                    rows.append(scene_metrics(scene, sel))
                    sels.append(sel)
                result[str(context)][measure][key] = aggregate(rows, sels)
    return result


def growth(scenes, args, others, context):
    if len({s.number for s in scenes}) < 2:
        return {}
    out = {}
    for key, name, mode in variants():
        points = []
        for scene in scenes:
            params = Params(budget(context, args, others.get(scene.scene_id), 'conservative'), 'conservative', mode,
                            core_recent_scenes=args.core_recent)
            points.append((scene.number, STRATEGIES[name](scene, params).chars))
        slope, intercept = fit_linear(points)
        out[key] = {'slope_chars': round(slope, 1), 'intercept_chars': round(intercept, 1),
                    'projected': {str(n): round(slope * n + intercept) for n in (300, 3000)}}
    return out


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
    report = {
        'story': {'scene_count': len(scenes), 'skipped': skipped,
                  'protagonist_id': scenes[0].protagonist if scenes else None,
                  'first_meetings_total': sum(s.first_meetings for s in scenes),
                  'other_context_source': {'attempt': sum(1 for o in others.values() if o),
                                           'share': sum(1 for o in others.values() if not o)}},
        'real': evaluate(scenes, others, args, contexts, MEASURES),
        'memory_stage': memory_stage,
        'growth': growth(scenes, args, others, biggest),
        'synthetic': synthetic,
        'control_cases': cases,
        'params': {'context': contexts, 'output_reserve': args.output_reserve, 'other_context': args.other_context,
                   'memory_share': args.memory_share, 'core_recent': args.core_recent, 'seed': args.seed,
                   'chars_per_token': CHARS_PER_TOKEN, 'synthetic': _ints(args.synthetic)},
    }
    return report, None


def main(argv=None):
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
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args(argv)
    report, error = run(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
