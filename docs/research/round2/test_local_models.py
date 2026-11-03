"""Temporary model registration and native load lifecycle, no live server."""
import json
import os
import socket

import httpx
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a,**k):raise AssertionError('No real socket in local lifecycle tests')
    monkeypatch.setattr(socket.socket,'connect',denied)


def test_registration_hardlinks_without_copy(tmp_path):
    from .local_models import register
    source=tmp_path/'source.gguf';source.write_bytes(b'synthetic-gguf')
    root=tmp_path/'models';root.mkdir()
    links=register({'L1':source},root)
    assert os.path.samefile(source,links['L1'])
    assert 'r28l-l1' in links['L1'].name


def test_registration_refuses_existing_namespace(tmp_path):
    from .local_models import register
    root=tmp_path/'models';(root/'round2-r28l').mkdir(parents=True)
    source=tmp_path/'source.gguf';source.write_bytes(b'untouched')
    with pytest.raises(ValueError,match='namespace'):register({'L1':source},root)
    assert source.read_bytes()==b'untouched'


def test_registration_rejects_unknown_label(tmp_path):
    from .local_models import register
    with pytest.raises(ValueError):register({'../evil':tmp_path/'file'},tmp_path/'models')


def test_owned_cleanup_preserves_source_and_other_files(tmp_path):
    from .local_models import register,cleanup
    source=tmp_path/'source.gguf';source.write_bytes(b'synthetic')
    root=tmp_path/'models';root.mkdir();links=register({'L1':source},root)
    other=links['L1'].parent/'owner-note.txt';other.write_text('keep')
    cleanup({'L1':source},links,root)
    assert source.exists() and other.exists() and not links['L1'].exists()


def test_cleanup_refuses_replaced_link(tmp_path):
    from .local_models import register,cleanup
    source=tmp_path/'source.gguf';source.write_bytes(b'synthetic')
    root=tmp_path/'models';root.mkdir();links=register({'L1':source},root)
    links['L1'].unlink();links['L1'].write_bytes(b'new owner data')
    with pytest.raises(ValueError,match='identity'):cleanup({'L1':source},links,root)
    assert links['L1'].read_bytes()==b'new owner data'


def test_load_guard_does_not_unload_existing_model():
    from .local_models import loaded_model
    calls=[]
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200,json={'models':[{'key':'owner','loaded_instances':[{'id':'owner-instance'}]}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='already loaded'):
            with loaded_model(client,'research',131072):pytest.fail('yielded')
    assert calls==['GET']


@pytest.mark.parametrize('wrong_config',[False,True])
def test_native_unloads_own_instance_on_error(wrong_config):
    from .local_models import loaded_model
    posts=[]
    def handler(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[]})
        body=json.loads(request.content);posts.append((request.url.path,body))
        if request.url.path.endswith('/load'):
            config={k:v for k,v in body.items() if k not in {'model','echo_load_config'}}
            if wrong_config:config['context_length']=8192
            return httpx.Response(200,json={'instance_id':'research-instance','status':'loaded','load_config':config})
        return httpx.Response(200,json={'instance_id':body['instance_id']})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((RuntimeError,ValueError)):
            with loaded_model(client,'research',131072) as result:
                assert result['instance_id']=='research-instance'
                raise RuntimeError('synthetic failure after load')
    assert posts[-1]==('/api/v1/models/unload',{'instance_id':'research-instance'})
    assert posts[0][1]['eval_batch_size']==512


def test_frozen_load_rejects_template_drift_and_wrong_catalog_size():
    from .local_models import loaded_model
    expected=dict(context_length=32768,eval_batch_size=512,flash_attention=True,
                  offload_kv_cache_to_gpu=True,prompt_template={'template':'original'})
    unloaded=[]
    def handler(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[dict(key='l3',size_bytes=123,loaded_instances=[])]})
        if request.url.path.endswith('/unload'):
            unloaded.append(1);return httpx.Response(200,json={})
        return httpx.Response(200,json=dict(instance_id='owned',load_config=dict(expected,prompt_template={'template':'changed'})))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='profile'):
            with loaded_model(client,'l3',32768,expected_profile=expected,expected_size=123):pytest.fail('yielded')
        with pytest.raises(ValueError,match='identity'):
            with loaded_model(client,'l3',32768,expected_profile=expected,expected_size=456):pytest.fail('yielded')
    assert unloaded==[1]


def test_frozen_import_rejects_replaced_hardlink(tmp_path):
    from .local_models import verify_imports
    source=tmp_path/'source.gguf';source.write_bytes(b'original')
    link=tmp_path/'link.gguf';os.link(source,link)
    registry=dict(sources={'L1':str(source)},links={'L1':str(link)})
    models={'L1':dict(path=str(source),bytes=8)}
    verify_imports(models,registry)
    link.unlink();link.write_bytes(b'replaced')
    with pytest.raises(ValueError,match='import'):verify_imports(models,registry)
