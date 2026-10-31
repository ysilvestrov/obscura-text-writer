import json
from storygen.token_budget.local_cli import main
from storygen.token_budget.local_profiles import select_snapshot
from tests.token_budget.test_local_counter import artifacts,body


def test_cli_qualification_and_explicit_activation(tmp_path,capsys):
    t,p=artifacts(tmp_path);evidence=tmp_path/'evidence.json'
    evidence.write_text(json.dumps([dict(request=body(),observed_tokens=2)]),encoding='utf-8')
    root=tmp_path/'data'
    assert main(['--data-dir',str(root),'register','--endpoint','http://localhost:1235/v1','--tokenizer',str(t),'--template',str(p),'--evidence',str(evidence)])==0
    profile=json.loads(capsys.readouterr().out)
    assert select_snapshot(root,'local','http://localhost:1235/v1',body()) is None
    assert main(['--data-dir',str(root),'activate','--id',profile['id']])==0
    assert select_snapshot(root,'local','http://localhost:1235/v1',body())['id']==profile['id']
    assert main(['--data-dir',str(root),'deactivate','--id',profile['id']])==0
    assert select_snapshot(root,'local','http://localhost:1235/v1',body()) is None


def test_bad_evidence_does_not_activate_or_echo_text(tmp_path,capsys):
    t,p=artifacts(tmp_path);e=tmp_path/'e.json'
    e.write_text(json.dumps([dict(request=body(),observed_tokens=999)]),encoding='utf-8')
    assert main(['--data-dir',str(tmp_path/'data'),'register','--endpoint','http://localhost:1235/v1','--tokenizer',str(t),'--template',str(p),'--evidence',str(e),'--activate'])==2
    assert 'System' not in capsys.readouterr().out
