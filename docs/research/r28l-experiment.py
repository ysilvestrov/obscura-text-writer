"""Round-two preparation and explicitly gated frozen quality dispatch."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['candidate','prepare','activate','quality','timing'])
    parser.add_argument('--snapshot',type=Path,default=Path('artifacts/round-2/freeze-candidate.json'))
    parser.add_argument('--review',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--exclusive-window-approved',action='store_true')
    parser.add_argument('--performance-window-approved',action='store_true',help='AC power, performance mode, no competing workload; timing only')
    parser.add_argument('--max-groups',type=int,default=1,help='New configuration/block groups per invocation; cached groups do not count')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    from round2.runner import atomic_json,digest
    from round2.freeze import workspace_candidate,workspace_prepare,workspace_inputs,activate_candidate,verify_snapshot,source_inventory,primary_config
    def read(path):return json.loads(path.read_text(encoding='utf-8'))
    if args.action=='candidate':
        if args.snapshot.exists():raise ValueError('Candidate exists; use a new output path instead of overwriting evidence')
        candidate=workspace_candidate(root);atomic_json(args.snapshot,candidate)
        print(json.dumps(workspace_prepare(root,candidate,verify_weights=False),ensure_ascii=False,indent=2))
        return 0
    frozen=read(args.snapshot)
    preview=workspace_prepare(root,frozen)
    if args.action=='prepare':
        print(json.dumps(preview,ensure_ascii=False,indent=2));return 0
    if args.action=='activate':
        if not args.review or not args.output:raise ValueError('Review record and new frozen output path required')
        if args.output.exists():raise ValueError('Frozen output already exists; never overwrite')
        active=activate_candidate(frozen,read(args.review));atomic_json(args.output,active)
        print('Frozen snapshot activated; no inference');return 0
    if not frozen['metadata']['activated']:raise ValueError('Candidate is not an activated freeze')
    if not args.exclusive_window_approved or args.max_groups<1:raise ValueError('Exclusive GPU/API window and positive group cap required')
    import httpx
    from dotenv import dotenv_values
    from round2.dev import gpu_snapshot
    from round2.local_models import loaded_model,verify_imports
    from round2.experiment import execute_schedule,frozen_send,timing_schedule
    # Key loading only after all offline gates and explicit dispatch action.
    for key in (['GOOGLE_API_KEY','ANTHROPIC_API_KEY'] if args.action=='quality' else []):
        value=os.environ.get(key) or dotenv_values(root/'.env').get(key)
        if not value:raise ValueError('Missing required API key: '+key)
        os.environ[key]=value
    manifest,cases,configs,models,paths=workspace_inputs(root)
    registry=read(root/'artifacts/round-2/preflight/model-links.json')
    if args.action=='timing':
        if not args.performance_window_approved:raise ValueError('Timing needs an approved performance window')
        from round2.dev import old_cases
        cases=old_cases();schedule=timing_schedule(cases,configs);contracts=frozen['metadata']['timing_contracts']
    else:schedule=frozen['metadata']['schedule'];contracts=frozen['metadata']['contracts']
    old_sources=set(source_inventory(root));other_paths=set(paths)-old_sources
    def guard():
        verify_snapshot(root,frozen,source_inventory(root)+list(other_paths))
        current=read(root/'docs/research/round2/manifest.json')
        if digest(primary_config(current))!=frozen['metadata']['configuration_sha256']:
            raise ValueError('Frozen configuration changed')
    with httpx.Client(trust_env=False) as client:
        instances={}
        @contextmanager
        def session(label,cfg):
            verify_imports(models,registry)
            with loaded_model(client,cfg['model'],cfg['context_tokens'],
                expected_profile=frozen['metadata']['native_load_profiles'][label],
                expected_size=models[label]['bytes']) as loaded:
                instances[label]=loaded.get('instance_id') or loaded['model_instance_id']
                try:yield loaded
                finally:instances.pop(label,None)
        send=frozen_send(client,root,{c['id']:c for c in cases},configs,contracts,gpu=gpu_snapshot,instances=instances)
        result=execute_schedule(root/f'artifacts/round-2/{args.action}',schedule,configs,
            frozen['snapshot_sha256'],send,session,guard,authorized=True,max_groups=args.max_groups)
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
