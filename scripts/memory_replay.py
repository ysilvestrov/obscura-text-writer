"""Read-only offline replay of stored memory responses: prints counters and codes only."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from storygen.memory.replay import collect, summarize  # noqa: E402


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='data/storygen.sqlite3')
    parser.add_argument('--data',default='data')
    parser.add_argument('--story')
    args=parser.parse_args(argv)
    if not Path(args.db).is_file():
        print('db_unavailable',file=sys.stderr);return 2
    try:rows=collect(Path(args.db),Path(args.data),args.story)
    except Exception:
        print('db_unreadable',file=sys.stderr);return 2
    print(json.dumps(summarize(rows),sort_keys=True,ensure_ascii=True,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
