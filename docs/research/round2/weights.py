"""Pinned research weights, bounded storage, and safe tool extraction. No inference."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def safe_name(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or not name:
        raise ValueError('Unsafe artifact path')
    return name


def validate_metadata(row):
    if not re.fullmatch('[0-9a-f]{40}',row['revision']):raise ValueError('Pinned revision required')
    for file in row['files']:
        safe_name(file['name'])
        if type(file['size']) is not int or file['size']<=0:raise ValueError('File size required')


def allowed_model_file(name):
    safe_name(name)
    return PurePosixPath(name).suffix in {'.safetensors','.json','.model','.txt','.jinja','.md'}


def require_space(root,additional,budget):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    used=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if additional<0 or used+additional>budget:raise ValueError('Research storage budget exceeded')
    if shutil.disk_usage(root).free<additional:raise ValueError('Insufficient free disk space')
    return used


def unpack_verified(archive,destination,checksum):
    archive=Path(archive);destination=Path(destination).resolve()
    if file_hash(archive)!=checksum:raise ValueError('Tool archive checksum mismatch')
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            safe_name(item.filename)
            if not (destination/item.filename).resolve().is_relative_to(destination):raise ValueError('Archive path escapes root')
            if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink rejected')
        destination.mkdir(parents=True,exist_ok=True);bundle.extractall(destination)


def require_approved_holdout(folder,manifest):
    if manifest.get('holdout_approved') is not True:raise ValueError('Holdout is not approved')
    if file_hash(Path(folder)/'holdout.json')!=manifest['holdout_sha256']:raise ValueError('Holdout hash mismatch')


def conversion_commands(python,converter,quantizer,source,intermediate,output):
    return ([str(python),str(converter),str(source),'--outfile',str(intermediate),'--outtype','f16'],
            [str(quantizer),str(intermediate),str(output),'Q4_K_M'])


def preparation_metadata():
    return json.loads(Path(__file__).with_name('weights-provenance.json').read_text(encoding='utf-8'))


def require_download_client(version):
    if version!=preparation_metadata()['download_client']:
        raise ValueError('Use pinned isolated download client with verified persistent resume')
