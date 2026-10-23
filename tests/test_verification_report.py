from pathlib import Path

import pytest

from scripts.verify import validate_args, summarize, render_status, run_verification


@pytest.mark.parametrize('args',[['--collect-only'],['--co'],['--collect-only=true'],['--junitxml=old.xml'],['-o','addopts=--collect-only']])
@pytest.mark.req('DOCS-STATUS')
def test_collection_is_rejected(args):
    with pytest.raises(ValueError):validate_args(args)


@pytest.mark.parametrize('code,xml',[(1,'<testsuite tests="1"><testcase name="ok"/></testsuite>'),(0,'bad xml'),(0,None),(5,'<testsuite tests="0"/>'),(0,'<testsuite tests="1"><testcase name="skip"><skipped/></testcase></testsuite>')])
@pytest.mark.req('DOCS-STATUS')
def test_failure_cannot_be_reported_as_passed(code,xml):
    assert summarize(code,xml)['state']!='passed'


def test_actual_results_keep_failures_errors_and_skips_separate():
    xml='<testsuites><testsuite tests="4"><testcase name="ok"/><testcase name="bad"><failure/></testcase><testcase name="err"><error/></testcase><testcase name="skip"><skipped/></testcase></testsuite></testsuites>'
    result=summarize(1,xml)
    assert result==dict(state='failed',passed=1,failed=1,errors=1,skipped=1,reported=4)
    assert summarize(0,'<testsuite tests="1"><testcase name="ok"/></testsuite>')['state']=='passed'


def test_inconsistent_junit_counts_cannot_claim_success():
    assert summarize(0,'<testsuite tests="2"><testcase name="only-one"/></testsuite>')['state']=='unconfirmed'


@pytest.mark.parametrize('counter',['failures','errors','skipped'])
def test_contradictory_suite_outcomes_are_not_success(counter):
    assert summarize(0,f'<testsuite tests="1" {counter}="1"><testcase name="ok"/></testsuite>')['state']=='unconfirmed'


def test_status_names_snapshot_command_and_actual_execution():
    data=dict(commit='abc123',dirty=True,snapshot_sha256='hash',started_at='2026-10-21T12:00:00+00:00',finished_at='2026-10-21T12:01:00+00:00',duration_seconds=60,command=['python','-m','pytest','tests/one.py'],exit_code=0,result=summarize(0,'<testsuite tests="1"><testcase name="ok"/></testsuite>'))
    text=render_status(data)
    for value in ['abc123','hash','tests/one.py','passed: 1','skipped: 0','UTC']:assert value in text
    assert 'літературної' in text and 'collection' in text


def test_new_run_does_not_reuse_old_xml_and_nonzero_process_is_preserved(tmp_path):
    old=tmp_path/'artifacts/old';old.mkdir(parents=True)
    (old/'junit.xml').write_text('<testsuite tests="1"><testcase name="ok"/></testsuite>')
    calls=[]
    def runner(command,**kwargs):
        calls.append(command)
        class Result:returncode=2
        return Result()
    result=run_verification(tmp_path,['tests/synthetic.py'],runner=runner,identity=dict(commit='test',dirty=False,snapshot_sha256='test'))
    assert result['result']['state']=='unconfirmed' and result['exit_code']==2
    assert len(calls)==1
    assert '--junitxml='+str(old/'junit.xml') not in calls[0]
    assert (tmp_path/'docs/STATUS.md').is_file()


def test_runner_uses_actual_new_xml(tmp_path):
    def runner(command,**kwargs):
        path=Path(next(arg.split('=',1)[1] for arg in command if arg.startswith('--junitxml=')))
        path.write_text('<testsuites><testsuite tests="2"><testcase name="one"/><testcase name="two"><skipped/></testcase></testsuite></testsuites>')
        class Result:returncode=0
        return Result()
    data=run_verification(tmp_path,['tests/synthetic.py'],runner=runner,identity=dict(commit='test',dirty=False,snapshot_sha256='test'))
    assert data['result']['passed']==1 and data['result']['skipped']==1
    assert data['result']['state']=='passed'


def test_source_change_during_run_is_not_a_verified_snapshot(tmp_path,monkeypatch):
    from scripts import verify
    identities=iter([dict(commit='test',dirty=True,snapshot_sha256='before'),dict(commit='test',dirty=True,snapshot_sha256='after')])
    monkeypatch.setattr(verify,'source_identity',lambda root:next(identities))
    def runner(command,**kwargs):
        Path(next(arg.split('=',1)[1] for arg in command if arg.startswith('--junitxml='))).write_text('<testsuite tests="1"><testcase name="ok"/></testsuite>')
        class Result:returncode=0
        return Result()
    data=run_verification(tmp_path,[],runner=runner)
    assert data['result']['state']=='unconfirmed'
    assert data['source_changed_during_run']
