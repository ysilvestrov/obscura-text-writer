"""CODEX-SKILLS: exercise the actual checkout CLI in isolated subprocess profiles."""
import dataclasses
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/install_codex_skills.py'


def run_cli(tmp_path, *args, cwd=None):
    env=os.environ.copy()
    env.update(USERPROFILE=str(tmp_path/'home'),HOME=str(tmp_path/'home'),CODEX_HOME=str(tmp_path/'codex'))
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    return subprocess.run([sys.executable,'-X','utf8',str(SCRIPT),*map(str,args)],
                          cwd=cwd or tmp_path,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)


def files(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.req('CODEX-SKILLS')
def test_cli_output_is_deterministic(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b'
    first=run_cli(tmp_path,'--output',a)
    second=run_cli(tmp_path,'--output',b)
    assert first.returncode == second.returncode == 0, first.stderr
    assert json.loads(first.stdout)['result'] == 'generated'
    assert len(json.loads(first.stdout)['names']) == 5
    assert files(a) == files(b)
    assert len(list(a.glob('*/SKILL.md'))) == 5


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('args',[[],['--output','out','--install']])
def test_cli_requires_one_destination(tmp_path,args):
    result=run_cli(tmp_path,*args)
    assert result.returncode == 2 and 'usage:' in result.stderr
    assert not (tmp_path/'home/.agents').exists() and not (tmp_path/'out').exists()


@pytest.mark.req('CODEX-SKILLS')
def test_cli_refuses_nonempty_output(tmp_path):
    target=tmp_path/'out'
    target.mkdir()
    (target/'author.txt').write_text('notes')
    result=run_cli(tmp_path,'--output',target)
    assert result.returncode == 1 and json.loads(result.stdout)['result'] == 'failed'
    assert files(target) == {'author.txt':b'notes'}


@pytest.mark.req('CODEX-SKILLS')
def test_cli_installs_into_temporary_profile(tmp_path):
    result=run_cli(tmp_path,'--install')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['result'] == 'installed'
    assert len(list((tmp_path/'home/.agents/skills').glob('*/SKILL.md'))) == 5
    repeat=run_cli(tmp_path,'--install')
    assert repeat.returncode == 0 and json.loads(repeat.stdout)['result'] == 'unchanged'
    assert not (tmp_path/'codex/config.toml').exists()


@pytest.mark.req('CODEX-SKILLS')
def test_cli_uses_its_checkout_from_another_cwd(tmp_path):
    foreign=tmp_path/'other'
    (foreign/'integrations/claude/obscura').mkdir(parents=True)
    (foreign/'integrations/claude/obscura/SKILL.md').write_text('foreign-sentinel')
    result=run_cli(tmp_path,'--output',tmp_path/'out',cwd=foreign)
    assert result.returncode == 0, result.stderr
    assert not any(b'foreign-sentinel' in raw for raw in files(tmp_path/'out').values())


@pytest.mark.req('CODEX-SKILLS')
def test_cli_generation_failure_does_not_install(tmp_path,monkeypatch,capsys):
    source=tmp_path/'fixture'
    shutil.copytree(ROOT/'integrations/claude/obscura',source/'integrations/claude/obscura')
    path=source/'integrations/claude/obscura/skills/start-story/SKILL.md'
    path.write_text(path.read_text().replace('## Model','## Changed'),encoding='utf-8')
    spec=importlib.util.spec_from_file_location('codex_installer_test',SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module,'source_root',lambda:source)
    assert module.main(['--install']) == 1
    assert json.loads(capsys.readouterr().out)['result'] == 'failed'
    assert not (Path(os.environ['USERPROFILE'])/'.agents').exists()


@pytest.mark.req('CODEX-SKILLS')
def test_core_config_and_install_sequence(tmp_path):
    from storygen.codex_connect import write_config,config_status
    from storygen.codex_skills import generate_skills
    from storygen.codex_skill_install import install_skills
    path=tmp_path/'codex/config.toml'
    command=['C:/Obscura/obscura-mcp.exe','--data-dir',str(tmp_path/'stories')]
    assert write_config(path,command).result == 'configured'
    assert config_status(path,command)['state'] == 'configured'
    assert write_config(path,command).result == 'unchanged'
    bundle=generate_skills(ROOT/'integrations/claude/obscura')
    assert install_skills(bundle,tmp_path).result == 'installed'
    updated=dataclasses.replace(bundle,generator_version='test-update')
    assert install_skills(updated,tmp_path).result == 'installed'
    author=tmp_path/'.agents/skills/obscura-start-story/SKILL.md'
    author.write_text('author edit')
    assert install_skills(bundle,tmp_path).result == 'conflict'
    assert author.read_text() == 'author edit'


@pytest.mark.req('CODEX-SKILLS')
def test_cli_emits_json_with_unicode_path_on_legacy_stdout(tmp_path,monkeypatch):
    import io
    spec=importlib.util.spec_from_file_location('codex_legacy_stdout_test',SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer=io.BytesIO()
    stream=io.TextIOWrapper(buffer,encoding='cp1252')
    monkeypatch.setattr(sys,'stdout',stream)
    target=tmp_path/'Є output'
    assert module.main(['--output',str(target)])==0
    stream.flush()
    result=json.loads(buffer.getvalue().decode('ascii'))
    assert result['path']==str(target) and result['result']=='generated'
