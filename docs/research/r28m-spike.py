"""Round2b first gate only. Does not start A-prime, cloud or new holdout work."""
import argparse
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--authorized-local-spike',action='store_true')
    parser.add_argument('--max-groups',type=int)
    args=parser.parse_args()
    from round2b.spike import prepare,execute
    root=Path(__file__).resolve().parents[2];folder=root/'artifacts/round-2/diagnostics/spike-2b'
    if args.action=='prepare':
        m=prepare(root,folder)
        print(json.dumps(dict(calls=len(m['schedule']),sha256=m['sha256'],schema_diffs=m['schema_diffs']),ensure_ascii=False))
    else:
        import httpx
        with httpx.Client(trust_env=False) as client:
            result=execute(root,folder,client,authorized=args.authorized_local_spike,max_groups=args.max_groups)
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
