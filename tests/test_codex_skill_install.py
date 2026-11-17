"""CODEX-SKILLS: filesystem installation protects unmanaged and edited files."""
import dataclasses
import json
import os
from pathlib import Path

import pytest

from storygen.codex_skill_install import install_skills
from storygen.codex_skills import SkillBundle

NAMES = ('obscura-start-story','obscura-draft-scene','obscura-publish','obscura-series-bible','obscura-setup-models')


@pytest.fixture
def bundle():
    files = {name+'/SKILL.md': ('name: '+name+'\noriginal\n').encode() for name in NAMES}
    files[NAMES[0]+'/references/interview.md'] = b'reference\n'
    return SkillBundle(files, {'shared/rules.md': 'a'*64}, '1')


def tree(path):
    return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}


def update(bundle):
    return dataclasses.replace(bundle, files={key:value+b'updated\n' for key,value in bundle.files.items()},
                               generator_version='2')


@pytest.mark.req('CODEX-SKILLS')
def test_first_install_and_repeat(tmp_path, bundle):
    profile = tmp_path/'profile'
    result = install_skills(bundle, profile)
    assert result.result == 'installed' and set(result.installed) == set(NAMES)
    root = profile/'.agents/skills'
    for key, raw in bundle.files.items():
        assert (root/key).read_bytes() == raw
    manifest = json.loads((root/NAMES[0]/'.obscura-install.json').read_text())
    assert manifest['schema'] == 1 and manifest['generator_version'] == '1'
    assert not any(str(profile) in str(value) for value in manifest.values())
    repeat = install_skills(bundle, profile)
    assert repeat.result == 'unchanged' and not repeat.backups and not repeat.installed


@pytest.mark.req('CODEX-SKILLS')
def test_managed_update_creates_exact_backups(tmp_path, bundle):
    install_skills(bundle,tmp_path)
    before = {name:tree(tmp_path/'.agents/skills'/name) for name in NAMES}
    result = install_skills(update(bundle),tmp_path)
    assert result.result == 'installed' and len(result.backups) == 5
    for backup in result.backups:
        assert backup.is_relative_to(tmp_path/'.agents/obscura-backups')
        assert tree(backup) == before[backup.name]
    for key, raw in update(bundle).files.items():
        assert (tmp_path/'.agents/skills'/key).read_bytes() == raw


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('mutation', ['unmanaged','manifest','edit','missing','extra'])
def test_conflict_preflight_leaves_all_targets_untouched(tmp_path, bundle, mutation):
    install_skills(bundle,tmp_path)
    root = tmp_path/'.agents/skills'
    target = root/NAMES[0]
    if mutation == 'unmanaged':
        (target/'.obscura-install.json').unlink()
    elif mutation == 'manifest':
        (target/'.obscura-install.json').write_text('{}')
    elif mutation == 'edit':
        (target/'SKILL.md').write_text('author edit')
    elif mutation == 'missing':
        (target/'references/interview.md').unlink()
    else:
        (target/'author.txt').write_text('author notes')
    before = tree(root)
    report = install_skills(update(bundle),tmp_path)
    assert report.result == 'conflict' and NAMES[0] in report.conflicts
    assert tree(root) == before
    assert not list((tmp_path/'.agents').glob('obscura-backups/*'))


@pytest.mark.req('CODEX-SKILLS')
def test_reparse_target_is_refused_before_any_write(tmp_path, bundle):
    # Windows junctions do not require symlink privileges.
    agents = tmp_path/'.agents'
    agents.mkdir()
    outside = tmp_path/'author'
    outside.mkdir()
    (outside/'private.txt').write_text('keep')
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(outside),str(agents/'skills'))
    else:
        (agents/'skills').symlink_to(outside, target_is_directory=True)
    report = install_skills(bundle,tmp_path)
    assert report.result == 'conflict'
    assert tree(outside) == {'private.txt':b'keep'}
    assert not list(agents.glob('obscura-staging/*'))


@pytest.mark.req('CODEX-SKILLS')
def test_failed_third_rename_restores_original_trees(tmp_path, bundle, monkeypatch):
    install_skills(bundle,tmp_path)
    root = tmp_path/'.agents/skills'
    before = tree(root)
    original = os.replace
    calls = 0
    def fail_third(src, dst):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PermissionError('third rename')
        return original(src,dst)
    monkeypatch.setattr(os,'replace',fail_third)
    report = install_skills(update(bundle),tmp_path)
    assert report.result == 'failed' and not report.installed and report.restored
    assert tree(root) == before


@pytest.mark.req('CODEX-SKILLS')
def test_rollback_preserves_concurrent_author_edit(tmp_path, bundle, monkeypatch):
    install_skills(bundle,tmp_path)
    original = os.replace
    calls = 0
    edited = None
    def fail_with_edit(src, dst):
        nonlocal calls, edited
        calls += 1
        if calls == 2:
            result = original(src,dst)
            edited = Path(dst)/'SKILL.md'
            edited.write_text('author concurrent edit')
            return result
        if calls == 3:
            raise PermissionError('third rename')
        return original(src,dst)
    monkeypatch.setattr(os,'replace',fail_with_edit)
    report = install_skills(update(bundle),tmp_path)
    assert report.result == 'partial' and report.conflicts
    assert edited and edited.read_text() == 'author concurrent edit'
    assert report.backups and all(path.exists() for path in report.backups)


@pytest.mark.req('CODEX-SKILLS')
def test_backups_and_staging_are_not_discoverable(tmp_path, bundle):
    install_skills(bundle,tmp_path)
    install_skills(update(bundle),tmp_path)
    root = tmp_path/'.agents/skills'
    assert {str(p.relative_to(root)) for p in root.rglob('SKILL.md')} == {
        str(Path(name)/'SKILL.md') for name in NAMES}
    assert {p.name for p in root.iterdir()} == set(NAMES)


@pytest.mark.req('CODEX-SKILLS')
def test_busy_lock_refuses_without_changes(tmp_path, bundle):
    agents=tmp_path/'.agents'
    agents.mkdir()
    (agents/'.obscura-install.lock').mkdir()
    before=tree(agents)
    report=install_skills(bundle,tmp_path)
    assert report.result == 'conflict' and 'install_busy' in report.errors
    assert tree(agents) == before and not (agents/'skills').exists()


@pytest.mark.req('CODEX-SKILLS')
def test_unsafe_bundle_is_rejected_before_write(tmp_path, bundle):
    unsafe=dataclasses.replace(bundle,files={**bundle.files,'../outside.md':b'escape'})
    assert install_skills(unsafe,tmp_path).result == 'failed'
    assert not list(tmp_path.iterdir())


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('parent',['skills','obscura-staging','obscura-backups'])
def test_parent_redirect_during_staging_is_refused(tmp_path,bundle,monkeypatch,parent):
    import shutil
    from storygen import codex_skill_install as ci
    install_skills(bundle,tmp_path)
    agents=tmp_path/'.agents'
    redirected=agents/parent
    redirected.mkdir(exist_ok=True)
    outside=tmp_path/'outside'
    held=tmp_path/'held'
    original=ci._write_tree
    redirected_once=False
    before=None
    def redirect(path,files,*args,**kwargs):
        nonlocal redirected_once,before
        result=original(path,files,*args,**kwargs)
        if not redirected_once:
            shutil.copytree(redirected,outside)
            before=tree(outside)
            assert redirected.resolve().is_relative_to(tmp_path.resolve())
            redirected.rename(held)
            if os.name=='nt':
                import _winapi
                _winapi.CreateJunction(str(outside),str(redirected))
            else:
                redirected.symlink_to(outside,target_is_directory=True)
            redirected_once=True
        return result
    monkeypatch.setattr(ci,'_write_tree',redirect)
    report=install_skills(update(bundle),tmp_path)
    assert report.result in {'conflict','failed','partial'}
    assert tree(outside)==before


@pytest.mark.req('CODEX-SKILLS')
def test_rollback_does_not_restore_directory_deleted_after_publication(tmp_path,bundle,monkeypatch):
    import shutil
    install_skills(bundle,tmp_path)
    original=os.replace
    calls=0
    deleted=None
    def fail_after_author_deletion(src,dst):
        nonlocal calls,deleted
        calls+=1
        if calls==2:
            result=original(src,dst)
            deleted=Path(dst)
            assert deleted.resolve().is_relative_to(tmp_path.resolve())
            shutil.rmtree(deleted)
            return result
        if calls==3:
            raise PermissionError('third rename')
        return original(src,dst)
    monkeypatch.setattr(os,'replace',fail_after_author_deletion)
    report=install_skills(update(bundle),tmp_path)
    assert report.result=='partial' and NAMES[0] in report.conflicts
    assert deleted and not deleted.exists()


@pytest.mark.req('CODEX-SKILLS')
def test_conflict_on_not_yet_touched_target_is_named(tmp_path,bundle,monkeypatch):
    from storygen import codex_skill_install as ci
    install_skills(bundle,tmp_path)
    original=ci._write_tree
    changed=False
    def author_change(path,files,*args,**kwargs):
        nonlocal changed
        result=original(path,files,*args,**kwargs)
        if not changed:
            (tmp_path/'.agents/skills'/NAMES[-1]/'SKILL.md').write_text('author edit')
            changed=True
        return result
    monkeypatch.setattr(ci,'_write_tree',author_change)
    report=install_skills(update(bundle),tmp_path)
    assert report.result in {'conflict','failed','partial'}
    assert NAMES[-1] in report.conflicts
    assert (tmp_path/'.agents/skills'/NAMES[-1]/'SKILL.md').read_text()=='author edit'
