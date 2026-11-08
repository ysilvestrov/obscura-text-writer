"""Workspace response benchmark: timings and a result digest; prints IDs, times and hashes only."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from storygen.application.workspace_bench import run  # noqa: E402


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',help='copy of the data directory')
    parser.add_argument('--story',help='story id prefix')
    parser.add_argument('--synthetic',type=int,help='number of synthetic scenes')
    parser.add_argument('--workdir',help='directory for the synthetic story')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    if bool(args.synthetic)==bool(args.data) or (args.synthetic and not args.workdir):
        parser.error('use --data <dir> or --synthetic <N> --workdir <dir>')
    try:result=run(args.data,args.story,args.synthetic,args.workdir)
    except (LookupError,ValueError) as error:
        print(str(error),file=sys.stderr);return 2
    print(json.dumps(result,sort_keys=True,indent=None if args.json else 2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
