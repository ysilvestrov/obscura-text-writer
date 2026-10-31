"""Preparation tests only: no downloads, installs, GPU loads or conversion."""
import hashlib
from pathlib import Path
import zipfile

import pytest


def test_download_requires_pinned_revision():
    from .weights import validate_metadata
    row=dict(repo='Qwen/Qwen3.5-9B',revision='main',files=[dict(name='model.safetensors',size=10)])
    with pytest.raises(ValueError,match='revision'):validate_metadata(row)


def test_model_paths_cannot_escape():
    from .weights import validate_metadata
    row=dict(repo='Qwen/Qwen3.5-9B',revision='a'*40,files=[dict(name='../outside',size=10)])
    with pytest.raises(ValueError,match='path'):validate_metadata(row)


def test_zip_cannot_escape(tmp_path):
    from .weights import unpack_verified
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside','bad')
    with pytest.raises(ValueError,match='path'):
        unpack_verified(archive,tmp_path/'tools',hashlib.sha256(archive.read_bytes()).hexdigest())
    assert not (tmp_path/'outside').exists()


def test_archive_checksum_is_required(tmp_path):
    from .weights import unpack_verified
    archive=tmp_path/'tool.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('quantize.exe','synthetic')
    with pytest.raises(ValueError,match='checksum'):unpack_verified(archive,tmp_path/'tools','0'*64)


def test_budget_includes_existing_bytes(tmp_path):
    from .weights import require_space
    (tmp_path/'existing').write_bytes(b'12345678')
    with pytest.raises(ValueError,match='budget'):require_space(tmp_path,3,10)
    require_space(tmp_path,2,10)


def test_model_download_allowlist_excludes_code():
    from .weights import allowed_model_file
    assert allowed_model_file('model-00001-of-00004.safetensors')
    assert allowed_model_file('tokenizer.json')
    assert not allowed_model_file('model.py')
    assert not allowed_model_file('pytorch_model.bin')


def test_holdout_hash_guard(tmp_path):
    from .weights import require_approved_holdout
    (tmp_path/'holdout.json').write_bytes(b'[]\n')
    with pytest.raises(ValueError,match='approved'):
        require_approved_holdout(tmp_path,dict(holdout_approved=False))
    with pytest.raises(ValueError,match='hash'):
        require_approved_holdout(tmp_path,dict(holdout_approved=True,holdout_sha256='bad'))


def test_same_recipe_for_both_pairs():
    from .weights import conversion_commands
    recipes=[conversion_commands('python','convert.py','quantize.exe',f'L{i}',f'L{i}.f16.gguf',f'L{i}.Q4_K_M.gguf') for i in range(1,5)]
    for convert,quantize in recipes:
        assert convert[-2:]==['--outtype','f16']
        assert quantize[-1]=='Q4_K_M' and '--imatrix' not in quantize


def test_public_preparation_metadata_is_self_contained_and_pinned():
    from .weights import preparation_metadata
    public=preparation_metadata()
    assert len(public['models'])==5
    for row in public['models']:__import__('round2.weights',fromlist=['validate_metadata']).validate_metadata(row)
    assert len(public['toolchain']['commit'])==40
    assert len(public['toolchain']['source_archive_sha256'])==64
    assert public['download_client']=='0.36.2'


def test_download_client_must_have_verified_persistent_resume():
    from .weights import require_download_client
    require_download_client('0.36.2')
    with pytest.raises(ValueError,match='client'):require_download_client('2.3.0')
