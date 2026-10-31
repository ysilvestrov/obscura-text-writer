"""Temporary, owned imports and native Bionic lifecycle; no production role edits."""
from contextlib import contextmanager
import os
from pathlib import Path


BASE='http://localhost:1235'


def register(sources: dict,models_root: Path) -> dict:
    if not sources or any(label not in {'L1','L2','L3','L4','L5','L6'} for label in sources):raise ValueError('Invalid configuration label')
    if any(not Path(path).is_file() or Path(path).suffix.lower()!='.gguf' for path in sources.values()):raise ValueError('Missing GGUF')
    root=Path(models_root).resolve();namespace=root/'round2-r28l'
    if namespace.exists():raise ValueError('Research namespace already exists; reconcile ownership first')
    namespace.mkdir(parents=True);links={}
    try:
        for label,source in sources.items():
            folder=namespace/label;folder.mkdir()
            target=folder/f'r28l-{label.lower()}-research.gguf'
            os.link(Path(source).resolve(),target);links[label]=target
    except Exception:
        cleanup(sources,links,root)
        raise
    return links


def cleanup(sources: dict,links: dict,models_root: Path):
    namespace=Path(models_root).resolve()/'round2-r28l'
    for label,target in links.items():
        target=Path(target)
        if not target.resolve().is_relative_to(namespace):raise ValueError('Cleanup path outside owned namespace')
        if target.exists() and (target.is_symlink() or not os.path.samefile(sources[label],target)):
            raise ValueError('Model link identity changed; leave owner data untouched')
    for target in links.values():
        target=Path(target)
        if target.exists():target.unlink()
        try:target.parent.rmdir()
        except OSError:pass  # Preserve any owner files introduced during the study.
    try:namespace.rmdir()
    except OSError:pass


def inventory(client):
    response=client.get(BASE+'/api/v1/models',timeout=15);response.raise_for_status()
    data=response.json()
    if not isinstance(data,dict) or not isinstance(data.get('models'),list):raise ValueError('Invalid native inventory')
    return data['models']


def verify_imports(models,registry):
    if set(registry['sources'])!=set(registry['links']) or set(registry['sources'])!=set(models)-{'L5'}:
        raise ValueError('Research import registry incomplete')
    for label,source in registry['sources'].items():
        model=models[label];link=Path(registry['links'][label]);path=Path(model['path'])
        if (Path(source).resolve()!=path.resolve() or not link.is_file() or link.is_symlink()
                or not os.path.samefile(path,link) or link.stat().st_size!=model['bytes']):
            raise ValueError('Research import identity changed: '+label)


@contextmanager
def loaded_model(client,key: str,context_length: int,*,expected_profile=None,expected_size=None):
    """Only begins with an empty GPU inventory; unloads only the requested key.

    Native API docs: /developer/rest/{load,unload,list}. Research uses an exclusive
    local-API window; another caller's loaded models are never auto-unloaded.
    """
    before=inventory(client)
    if any(row.get('loaded_instances') for row in before):raise ValueError('A model is already loaded; coordinate with owner first')
    if expected_size is not None:
        selected=[r for r in before if r.get('key')==key]
        if len(selected)!=1 or selected[0].get('size_bytes')!=expected_size:
            raise ValueError('Native model catalogue identity differs from frozen weights')
    wanted=dict(context_length=context_length,eval_batch_size=512,flash_attention=True,offload_kv_cache_to_gpu=True)
    instance_id=None
    try:
        response=client.post(BASE+'/api/v1/models/load',json=dict(model=key,echo_load_config=True,**wanted),timeout=300)
        response.raise_for_status();data=response.json()
        instance_id=data.get('instance_id') or data.get('model_instance_id')
        if not instance_id:raise ValueError('Missing loaded instance identity')
        applied=data.get('load_config') or {}
        if any(applied.get(k)!=v for k,v in wanted.items()):raise ValueError('Native load config differs from requested profile')
        if expected_profile is not None and applied!=expected_profile:
            raise ValueError('Native full load profile differs from frozen dev profile')
        yield data
    finally:
        owned={instance_id} if instance_id else set()
        # Also recover a load whose HTTP response was lost after allocation.
        for row in inventory(client):
            if row.get('key')==key:owned.update(i['id'] for i in row.get('loaded_instances',[]) if i.get('id'))
        for id in owned:
            response=client.post(BASE+'/api/v1/models/unload',json=dict(instance_id=id),timeout=120)
            response.raise_for_status()
