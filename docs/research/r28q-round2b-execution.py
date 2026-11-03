"""A-prime/round2b guard, offline dry-run and execution freeze; no activation action."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['probe-backend','dry-run','freeze','verify','run'])
    p.add_argument('--authorized-quality',action='store_true')
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    from round2b.execution import load_input,load_execution,probe_backend,build_execution_freeze
    proof=root/'artifacts/round-2b/execution-preflight/backend-echo.json'
    if args.action=='probe-backend':
        echoes=probe_backend(root,proof);print(json.dumps(dict(backend_models=list(echoes),generation_calls=0)));return
    if args.action=='dry-run':
        _,a=load_input(root);echoes=json.loads(proof.read_text(encoding='utf-8'))['echoes']
        r=a.dry_run(root/'artifacts/round-2b/execution-dry-run',echoes)
        print(json.dumps({k:r[k] for k in ['slots','body_matches','http_calls','inference_calls','ledger_writes']}));return
    if args.action=='freeze':
        package=build_execution_freeze(root)
    else:
        if args.action=='run' and not args.authorized_quality:raise ValueError('Quality run is not authorized')
        package,a=load_execution(root)
        if args.action=='run':print(json.dumps(a.run(authorized=True)));return
    print(json.dumps(dict(execution_sha256=package['snapshot_sha256'],input_sha256=package['metadata']['input_sha256'],quality_authorized=False)))


if __name__=='__main__':main()
