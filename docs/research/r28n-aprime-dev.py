"""One initial A-prime dev iteration. Never freezes prompt or creates new holdout."""
import argparse
import json
import os
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--authorized-dev',action='store_true');args=parser.parse_args()
    from round2b.dev import prepare,execute
    root=Path(__file__).resolve().parents[2];folder=root/'artifacts/round-2b/dev/aprime-v1'
    if args.action=='prepare':
        m=prepare(root,folder);print(json.dumps({k:m[k] for k in ['calls','cloud_calls','reserves','total_reserve','available_before','prompt_sha256','sha256']},ensure_ascii=False));return
    if not args.authorized_dev:raise ValueError('Explicit dev authorization required')
    import httpx
    from dotenv import dotenv_values
    for key in ['GOOGLE_API_KEY','ANTHROPIC_API_KEY']:
        value=os.environ.get(key) or dotenv_values(root/'.env').get(key)
        if not value:raise ValueError('Missing key: '+key)
        os.environ[key]=value
    with httpx.Client(trust_env=False) as client:counts=execute(root,folder,client,authorized=True)
    print(json.dumps(counts,ensure_ascii=False))

if __name__=='__main__':main()
