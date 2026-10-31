"""Opt-in pinned downloads for the approved round-two study. Never loads GPU/models."""
import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values
import httpx

from round2.runner import atomic_json
from round2.weights import (allowed_model_file,file_hash,require_approved_holdout,require_space,unpack_verified,
                            validate_metadata,preparation_metadata,require_download_client)


ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'artifacts/round-2'
BUDGET=230_000_000_000  # decimal GB, explicitly approved by owner 28.10.2026


def download_tool(client,url,path,checksum=None):
    path=Path(path)
    if not path.exists():
        require_space(FOLDER,100_000_000,BUDGET)
        with client.stream('GET',url) as response:
            response.raise_for_status()
            with path.with_suffix(path.suffix+'.partial').open('wb') as file:
                for block in response.iter_bytes():file.write(block)
        path.with_suffix(path.suffix+'.partial').replace(path)
    actual=file_hash(path)
    if checksum is not None and actual!=checksum:raise ValueError('Downloaded tool checksum mismatch')
    return actual


def prepare_tools():
    release=preparation_metadata()['toolchain']
    commit=release['commit']
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('Unpinned converter')
    asset=next(a for a in release['assets'] if a['name'].endswith('win-cpu-x64.zip'))
    tools=FOLDER/'tooling';tools.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=120,trust_env=False,follow_redirects=True) as client:
        binary=tools/asset['name'];binary_sha=download_tool(client,asset['url'],binary,asset['digest'].removeprefix('sha256:'))
        unpack_verified(binary,tools/'cpu',binary_sha)
        source=tools/'llama-source.zip';source_sha=download_tool(client,'https://api.github.com/repos/ggml-org/llama.cpp/zipball/'+commit,
                                                               source,release['source_archive_sha256'])
        unpack_verified(source,tools/'source',source_sha)
    source_roots=list((tools/'source').glob('ggml-org-llama.cpp-*'))
    if len(source_roots)!=1 or not source_roots[0].name.endswith(commit[:7]):raise ValueError('Unexpected source root')
    state=dict(tag=release['tag'],commit=commit,binary_sha256=binary_sha,source_archive_sha256=source_sha,
               source=str(source_roots[0].relative_to(ROOT)),imatrix=False,output_type='f16',quantization='Q4_K_M')
    atomic_json(FOLDER/'preflight/toolchain.json',state)
    print(json.dumps(state),flush=True)


def download_weights():
    # Set all HF caches before lazy import; keep downloads inside approved workspace.
    os.environ['HF_HOME']=str(FOLDER/'hf-home')
    os.environ['HF_XET_CACHE']=str(FOLDER/'hf-home/xet')
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
    os.environ['HF_HUB_DISABLE_XET']='1'  # avoid a second large chunk cache outside per-file accounting
    os.environ['HF_HUB_VERBOSITY']='error'
    from huggingface_hub import HfApi,hf_hub_download,__version__
    require_download_client(__version__)
    token=os.environ.get('HF_TOKEN') or dotenv_values(ROOT/'.env').get('HF_TOKEN')
    if not token:raise ValueError('HF_TOKEN required for gated Gemma')
    rows=preparation_metadata()['models']
    api=HfApi(endpoint='https://huggingface.co',token=token)
    records=[]
    for label,row in zip(['L1','L2','L3','L4','L6'],rows,strict=True):
        validate_metadata(row)
        expected=('Qwen/Qwen3.5-9B','huihui-ai/Huihui-Qwen3.5-9B-abliterated','google/gemma-3-12b-it',
                  'INSAIT-Institute/MamayLM-Gemma-3-12B-IT-v2.0','unsloth/gemma-4-E4B-it-GGUF')[len(records)]
        if row['repo']!=expected:raise ValueError('Unexpected model metadata order')
        info=api.model_info(row['repo'],revision=row['revision'],files_metadata=True)
        entries=[f for f in info.siblings if (f.rfilename in {r['name'] for r in row['files']} if label=='L6' else allowed_model_file(f.rfilename))]
        folder=FOLDER/'weights'/label;folder.mkdir(parents=True,exist_ok=True);files=[]
        for index,item in enumerate(entries,1):
            if not item.size or item.size<=0:raise ValueError('Missing source file size')
            target=folder/item.rfilename
            need=0 if target.exists() and target.stat().st_size==item.size else item.size
            require_space(FOLDER,need,BUDGET)
            print(json.dumps(dict(model=label,file=item.rfilename,index=index,total=len(entries),bytes=item.size)),flush=True)
            path=Path(hf_hub_download(repo_id=row['repo'],filename=item.rfilename,revision=row['revision'],
                                    local_dir=folder,cache_dir=FOLDER/'hf-home/hub',token=token,endpoint='https://huggingface.co'))
            if path.stat().st_size!=item.size:raise ValueError('Downloaded size mismatch')
            checksum=file_hash(path)
            lfs=getattr(item,'lfs',None)
            expected_sha=getattr(lfs,'sha256',None) if lfs else None
            if expected_sha and expected_sha!=checksum:raise ValueError('Downloaded source hash mismatch')
            files.append(dict(file=item.rfilename,bytes=item.size,sha256=checksum))
        records.append(dict(configuration=label,repo=row['repo'],revision=row['revision'],files=files))
        atomic_json(FOLDER/'preflight/downloads.json',records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--tools-only',action='store_true')
    args=parser.parse_args()
    require_approved_holdout(ROOT/'docs/research/round2',json.loads((ROOT/'docs/research/round2/manifest.json').read_text(encoding='utf-8')))
    if not args.run:
        print('No downloads: pass --run only within owner-approved 230GB permission');return 0
    prepare_tools()
    if not args.tools_only:download_weights()
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        # Never print credential-bearing HTTP exception strings or environment.
        print('Preparation stopped: '+type(error).__name__+'; no model inference performed',file=sys.stderr)
        raise SystemExit(1)
