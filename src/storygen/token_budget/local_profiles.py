"""Content-addressed optional local counters and explicit activation. No network."""
import hashlib
import json
import re
import stat
from importlib.metadata import version,PackageNotFoundError
from functools import lru_cache
from pathlib import Path
from .core import digest,endpoint_identity
from .local_counter import CounterUnavailable,REVISION,admitted,count_known
from ..storage.files import FileStore

ID=re.compile(r'^[0-9a-f]{64}$')


def checked_file(root,relative,limit):
    base=Path(root).absolute();path=base/relative
    if not path.resolve().is_relative_to(base.resolve()):raise CounterUnavailable('local_counter_unsafe_path')
    current=path
    while current!=base.parent:
        try:info=current.lstat()
        except OSError as exc:raise CounterUnavailable('local_counter_file_missing') from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:raise CounterUnavailable('local_counter_unsafe_path')
        if current==base:break
        current=current.parent
    if not path.is_file() or path.stat().st_size>limit:raise CounterUnavailable('local_counter_invalid_file')
    return path


@lru_cache(maxsize=1)
def _runtime_versions():
    try:return tuple((name,version(name)) for name in ['tokenizers','jinja2'])
    except PackageNotFoundError as exc:raise CounterUnavailable('local_counter_dependency_unavailable') from exc


def runtime_versions():return dict(_runtime_versions())

def metadata(root,id):
    if not isinstance(id,str) or not ID.fullmatch(id):raise CounterUnavailable('local_counter_invalid_id')
    try:p=json.loads(checked_file(root,f'local_tokenizers/{id}/profile.json',65536).read_text(encoding='utf-8'))
    except (ValueError,OSError) as exc:raise CounterUnavailable('local_counter_invalid_profile') from exc
    if not isinstance(p,dict):raise CounterUnavailable('local_counter_invalid_profile')
    if p.get('id')!=id or digest({k:v for k,v in p.items() if k!='id'})!=id or p.get('revision')!=REVISION:raise CounterUnavailable('local_counter_profile_hash_mismatch')
    return p


def binding(p):return digest([p['model'],p['endpoint'],p['system_sha256']])


def active_ids(root):
    try:
        data=json.loads(checked_file(root,'local_tokenizers/active.json',65536).read_text(encoding='utf-8'))
        if not isinstance(data,dict):raise CounterUnavailable('local_counter_invalid_registry')
        return data
    except (CounterUnavailable,ValueError):return {}


def activate(root,id):
    p=metadata(root,id);load_counter(root,p,require_active=False,verify_bytes=True)
    active=active_ids(root);active[binding(p)]=id
    FileStore(Path(root)).write('local_tokenizers/active.json',json.dumps(active,sort_keys=True).encode())
    return p


def select_snapshot(root,provider,endpoint,body):
    if provider!='local':return None
    try:
        key=digest([body.get('model'),endpoint_identity(endpoint),digest(body['messages'][0]['content'])])
        id=active_ids(root).get(key)
        if not id:return None
        p=metadata(root,id)
        if p['endpoint']!=endpoint_identity(endpoint) or not admitted(body,p):return None
        return p
    except (CounterUnavailable,ValueError,TypeError,KeyError):return None


@lru_cache(maxsize=4)
def compiled(tokenizer_path,tokenizer_stamp,tokenizer_sha,template_path,template_stamp,template_sha):
    try:
        from tokenizers import Tokenizer
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        t=Path(tokenizer_path).read_bytes();p=Path(template_path).read_bytes()
        if hashlib.sha256(t).hexdigest()!=tokenizer_sha or hashlib.sha256(p).hexdigest()!=template_sha:raise CounterUnavailable('local_counter_artifact_hash_mismatch')
        template=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True).from_string(p.decode('utf-8'))
        tokenizer=Tokenizer.from_str(t.decode('utf-8'))
        tokenizer.no_truncation();tokenizer.no_padding()
        return tokenizer,template
    except CounterUnavailable:raise
    except Exception as exc:raise CounterUnavailable('local_counter_dependency_or_artifact_unavailable') from exc


def load_counter(root,snapshot,require_active=True,verify_bytes=False):
    p=metadata(root,snapshot.get('id'))
    if p.get('runtime_versions')!=runtime_versions():raise CounterUnavailable('local_counter_runtime_mismatch')
    if p!=snapshot:raise CounterUnavailable('local_counter_snapshot_mismatch')
    if require_active and active_ids(root).get(binding(p))!=p['id']:raise CounterUnavailable('local_counter_not_active')
    folder=f"local_tokenizers/{p['id']}"
    t=checked_file(root,folder+'/tokenizer.json',20000000);s=checked_file(root,folder+'/chat-template.txt',65536)
    if verify_bytes:
        for file,key in [(t,'tokenizer_sha256'),(s,'template_sha256')]:
            if hashlib.sha256(file.read_bytes()).hexdigest()!=p[key]:raise CounterUnavailable('local_counter_artifact_hash_mismatch')
    def stamp(path):
        v=path.stat();return (v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    tokenizer,template=compiled(str(t),stamp(t),p['tokenizer_sha256'],str(s),stamp(s),p['template_sha256'])
    return p,tokenizer,template


def register(root,endpoint,request,tokenizer_path,template_path,evidence):
    from ..providers.models import ProviderSettings
    ProviderSettings(provider='local',model=request['model'],base_url=endpoint)
    source_t=Path(tokenizer_path).absolute();source_s=Path(template_path).absolute()
    t=checked_file(source_t.parent,source_t.name,20000000).read_bytes();s=checked_file(source_s.parent,source_s.name,65536).read_bytes()
    p=dict(revision=REVISION,runtime_versions=runtime_versions(),model=request['model'],endpoint=endpoint_identity(endpoint),tokenizer_sha256=hashlib.sha256(t).hexdigest(),template_sha256=hashlib.sha256(s).hexdigest(),system_sha256=digest(request['messages'][0]['content']),evidence=[])
    if not admitted(request,p) or not evidence:raise CounterUnavailable('local_counter_qualification_required')
    # Compile and qualify before writing anything to the production data root.
    tokenizer,template=compiled(str(source_t),(source_t.stat().st_mtime_ns,),p['tokenizer_sha256'],str(source_s),(source_s.stat().st_mtime_ns,),p['template_sha256'])
    for item in evidence:
        observed=item['observed_tokens']
        if type(observed) is not int or observed<=0 or count_known(item['request'],(p,tokenizer,template))!=observed:raise CounterUnavailable('local_counter_usage_mismatch')
        p['evidence'].append(dict(request_sha256=digest(item['request']),observed_tokens=observed))
    p['id']=digest(p);store=FileStore(Path(root));folder='local_tokenizers/'+p['id']
    store.write(folder+'/tokenizer.json',t);store.write(folder+'/chat-template.txt',s)
    store.write(folder+'/profile.json',json.dumps(p,ensure_ascii=False,sort_keys=True).encode('utf-8'))
    return p


def deactivate(root,id):
    p=metadata(root,id);active=active_ids(root)
    if active.get(binding(p))==id:active.pop(binding(p))
    FileStore(Path(root)).write('local_tokenizers/active.json',json.dumps(active,sort_keys=True).encode())
    return p
