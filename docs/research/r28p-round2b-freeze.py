"""Offline input-freeze package only; no dispatch or model/API client."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','verify'])
    p.add_argument('--environment',type=Path)
    p.add_argument('--owner-l3-admission',action='store_true')
    args=p.parse_args()
    from round2b.freeze import prepare,verify
    root=Path(__file__).resolve().parents[2]
    if args.action=='prepare':
        if not args.environment:p.error('--environment required')
        package=prepare(root,root/'artifacts/round-2b/quality',json.loads(args.environment.read_text(encoding='utf-8')),l3_approved=args.owner_l3_admission)
    else:
        package=json.loads((root/'docs/research/round2b/frozen-quality.json').read_text(encoding='utf-8'));verify(root,package)
    m=package['metadata']
    print(json.dumps(dict(snapshot_sha256=package['snapshot_sha256'],slots=m['slots'],local=m['local_slots'],cloud=m['cloud_slots'],reserve=m['cloud_total_reserve'],available=m['shared_available'],quality_authorized=m['quality_authorized']),ensure_ascii=False))


if __name__=='__main__':main()
