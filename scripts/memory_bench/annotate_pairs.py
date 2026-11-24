"""Annotation of planted pairs (#25): finds repeat-scene records that carry a pair's wording and stores confirmed claim IDs.

Story texts go only to the --out file outside the repository; stdout/stderr carry counts and codes, the annotation file IDs."""
import argparse
import json
import re
import sys
from pathlib import Path

from .extract import extract_story

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANNOTATION = ROOT / 'docs' / 'research' / 'data' / '2026-11-24-rag-pairs-annotation.json'
APOSTROPHES = "'’ʼ`"
STEM = 5
MIN_WORD = 4


class BenchError(Exception):
    """Carries a stable error code for stderr."""


def load_pairs(path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _normalize(text: str) -> str:
    return text.lower().translate({ord(c): None for c in APOSTROPHES})


def stems(words: str) -> tuple[str, ...]:
    found = (w for w in re.findall(r'\w+', _normalize(words)) if len(w) >= MIN_WORD)
    return tuple(dict.fromkeys(w[:STEM] for w in found))


def candidates(scenes, pair: dict) -> list:
    """Records of the repeat scene whose text contains the stem of any wording word."""
    wanted = stems(pair.get('first_words') or pair.get('words') or '')
    repeat = next((s for s in scenes if s.number == pair['repeat']), None)
    if repeat is None or not wanted:
        return []
    return [r for r in repeat.records if any(stem in _normalize(r.text) for stem in wanted)]


def _inside_repo(path) -> bool:
    return Path(path).resolve().is_relative_to(ROOT.resolve())


def _repeat_records(args):
    """Repeat-scene records by number for the chosen story, opened the way memory_retrieval_bench does."""
    from storygen.application.workspace_bench import _check_data_dir
    try:
        data = _check_data_dir(args.data, True)
    except ValueError as error:
        raise BenchError(str(error).split(':')[0])
    try:
        from storygen.storage.repository import Repository
        repo = Repository(data)
        stories = repo.list_stories()
    except Exception:
        raise BenchError('db_unreadable')
    chosen = [s for s in stories if s.id.startswith(args.story)]
    if not chosen:
        raise BenchError('story_not_found')
    story = max(chosen, key=lambda s: (len(repo.list_scenes(s.id)), s.id))
    scenes, _ = extract_story(repo, story.id)
    return story.id, scenes


def _entries(pairs: dict):
    return [*pairs.get('pairs', []), *pairs.get('controls', [])]


def propose(args) -> None:
    if _inside_repo(args.out):
        raise BenchError('inside_repo')
    _, scenes = _repeat_records(args)
    result = {p['id']: [{'claim_id': r.claim_id, 'category': r.category, 'text': r.text} for r in candidates(scenes, p)]
              for p in _entries(load_pairs(args.pairs))}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: len(v) for k, v in result.items()}, sort_keys=True))


def confirm(args) -> None:
    story_id, scenes = _repeat_records(args)
    entries = {p['id']: p for p in _entries(load_pairs(args.pairs))}
    picks = json.loads(Path(args.picks).read_text(encoding='utf-8'))
    if any(pair_id not in entries for pair_id in picks):
        raise BenchError('unknown_pair')
    known = {}
    for pair_id in picks:
        repeat = next((s for s in scenes if s.number == entries[pair_id]['repeat']), None)
        known[pair_id] = {r.claim_id for r in repeat.records} if repeat else set()
    if any(claim not in known[pair_id] for pair_id, ids in picks.items() for claim in ids):
        raise BenchError('unknown_claim')
    path = Path(args.annotation)
    document = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'stories': {}}
    document.setdefault('stories', {}).setdefault(story_id, {}).update({k: list(v) for k, v in picks.items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({k: len(v) for k, v in picks.items()}, sort_keys=True))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('propose', 'confirm'):
        p = sub.add_parser(name)
        p.add_argument('--data', required=True, help='copy of the data directory (the working one is refused)')
        p.add_argument('--story', required=True, help='story ID prefix')
        p.add_argument('--pairs', required=True)
        if name == 'propose':
            p.add_argument('--out', required=True, help='candidates file with texts; must lie outside the repository')
        else:
            p.add_argument('--picks', required=True, help='JSON {pair_id: [claim_id, ...]}')
            p.add_argument('--annotation', default=str(DEFAULT_ANNOTATION))
    args = parser.parse_args(argv)
    try:
        {'propose': propose, 'confirm': confirm}[args.command](args)
    except BenchError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
