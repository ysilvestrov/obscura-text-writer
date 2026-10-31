import json
import pytest
pytest.importorskip('tokenizers')
from tokenizers import Tokenizer,models,pre_tokenizers
from storygen.token_budget.local_counter import count_known,predict_body,CounterUnavailable
from storygen.token_budget.local_profiles import register,activate,select_snapshot,load_counter


def body():
    return dict(model='test-local',messages=[dict(role='system',content='System'),dict(role='user',content='{}')],reasoning_effort='none',response_format=dict(type='json_schema',json_schema=dict(name='impact_part',strict=True,schema={})))


def artifacts(root):
    tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'System':1,'{}':2},unk_token='[UNK]'));tokenizer.pre_tokenizer=pre_tokenizers.WhitespaceSplit()
    path=root/'tokenizer.json';tokenizer.save(str(path))
    template=root/'template.txt';template.write_text('{% for m in messages %}{{m.content}} {% endfor %}',encoding='utf-8')
    return path,template


def prepared(root):
    t,p=artifacts(root)
    profile=register(root/'data','http://localhost:1235/v1',body(),t,p,[dict(request=body(),observed_tokens=2)])
    return profile


def test_registration_is_inactive_and_counts_exact(tmp_path):
    profile=prepared(tmp_path)
    assert select_snapshot(tmp_path/'data','local','http://localhost:1235/v1',body()) is None
    activate(tmp_path/'data',profile['id'])
    snap=select_snapshot(tmp_path/'data','local','http://localhost:1235/v1',body())
    counter=load_counter(tmp_path/'data',snap)
    assert count_known(body(),counter)==2
    assert predict_body(body(),counter)['input_tokens']==514
    assert not any('System' in p.read_text(encoding='utf-8') for p in (tmp_path/'data').glob('**/profile.json'))


def test_unknown_child_uses_worst_case_not_repeated_emoji(tmp_path):
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id']);counter=load_counter(tmp_path/'data',profile)
    b=body();b['messages'][1]['content']=json.dumps(dict(response_character_limit=1000,results={'R1':{'reserved_result':'😀'*1000}},reserved_reference_overhead='x'*1024))
    estimate=predict_body(b,counter)
    assert estimate['input_tokens']>=4*1000+1024+512


def test_wrong_usage_and_scope_are_rejected(tmp_path):
    t,p=artifacts(tmp_path)
    with pytest.raises(ValueError):register(tmp_path/'data','http://localhost:1235/v1',body(),t,p,[dict(request=body(),observed_tokens=3)])
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id']);counter=load_counter(tmp_path/'data',profile)
    for change in [{'model':'other'},{'reasoning_effort':'high'},{'tools':[]}]:
        with pytest.raises(CounterUnavailable):count_known({**body(),**change},counter)


def test_hash_and_path_tampering_fail_closed(tmp_path):
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id'])
    path=tmp_path/'data'/'local_tokenizers'/profile['id']/'chat-template.txt'
    path.write_text('changed',encoding='utf-8')
    with pytest.raises(CounterUnavailable):load_counter(tmp_path/'data',profile)
    with pytest.raises(CounterUnavailable):load_counter(tmp_path/'data',{'id':'../escape'})


def test_template_cannot_access_python_internals(tmp_path):
    t,p=artifacts(tmp_path);p.write_text("{{ ''.__class__.__mro__ }}",encoding='utf-8')
    with pytest.raises(ValueError):register(tmp_path/'data','http://localhost:1235/v1',body(),t,p,[dict(request=body(),observed_tokens=2)])


def test_actual_known_body_is_not_reserialized(tmp_path):
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id']);counter=load_counter(tmp_path/'data',profile)
    b=body();b['messages'][1]['content']='{  "results" : {} }'
    assert predict_body(b,counter)['input_tokens']==count_known(b,counter)+512


def test_profile_survives_verified_backup(tmp_path):
    from storygen.storage.repository import Repository
    from storygen.storage.backup import create_backup,restore_backup
    root=tmp_path/'data';Repository(root)
    profile=prepared(tmp_path);activate(root,profile['id'])
    backup=create_backup(root,tmp_path/'backup');restored=restore_backup(backup,tmp_path/'restored')
    assert count_known(body(),load_counter(restored,profile))==2


def test_missing_optional_dependency_is_unavailable(tmp_path,monkeypatch):
    import builtins
    from storygen.token_budget.local_profiles import compiled
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id']);compiled.cache_clear()
    original=builtins.__import__
    def missing(name,*args,**kwargs):
        if name=='tokenizers':raise ImportError('optional')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',missing)
    with pytest.raises(CounterUnavailable):load_counter(tmp_path/'data',profile)


def test_runtime_version_mismatch_is_rejected(tmp_path,monkeypatch):
    from storygen.token_budget import local_profiles
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id'])
    monkeypatch.setattr(local_profiles,'runtime_versions',lambda:{'tokenizers':'changed','jinja2':'changed'})
    with pytest.raises(CounterUnavailable):load_counter(tmp_path/'data',profile)


def test_dispatch_rechecks_bytes_even_if_mtime_is_restored(tmp_path):
    import os
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id'])
    path=tmp_path/'data'/'local_tokenizers'/profile['id']/'chat-template.txt'
    before=path.stat();text=path.read_text(encoding='utf-8');path.write_text(text.replace('m.content','m.changed'),encoding='utf-8')
    os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
    with pytest.raises(CounterUnavailable):load_counter(tmp_path/'data',profile,verify_bytes=True)


@pytest.mark.parametrize('change',[{'messages':[None,None]},{'response_format':None},{'messages':'ab'}])
def test_malformed_shape_is_unavailable(tmp_path,change):
    profile=prepared(tmp_path);activate(tmp_path/'data',profile['id']);counter=load_counter(tmp_path/'data',profile)
    with pytest.raises(CounterUnavailable):count_known({**body(),**change},counter)


def test_serialized_truncation_cannot_hide_a_long_prompt(tmp_path):
    t,p=artifacts(tmp_path)
    tokenizer=Tokenizer.from_file(str(t));tokenizer.enable_truncation(max_length=10);tokenizer.save(str(t))
    profile=register(tmp_path/'data','http://localhost:1235/v1',body(),t,p,[dict(request=body(),observed_tokens=2)])
    activate(tmp_path/'data',profile['id']);counter=load_counter(tmp_path/'data',profile)
    long=body();long['messages'][1]['content']='word '*10000
    assert count_known(long,counter)==10001


def test_serialized_padding_is_not_part_of_chat_input_count(tmp_path):
    t,p=artifacts(tmp_path)
    tokenizer=Tokenizer.from_file(str(t));tokenizer.enable_padding(length=100,pad_id=0,pad_token='[UNK]');tokenizer.save(str(t))
    profile=register(tmp_path/'data','http://localhost:1235/v1',body(),t,p,[dict(request=body(),observed_tokens=2)])
    activate(tmp_path/'data',profile['id'])
    assert count_known(body(),load_counter(tmp_path/'data',profile))==2
