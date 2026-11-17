"""CODEX-SKILLS: install only managed trees; never erase an author's concurrent edits."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from .codex_skills import NAMES, SkillBundle

MANIFEST = '.obscura-install.json'
_NAMES = tuple('obscura-'+name for name in NAMES)


@dataclass(frozen=True)
class InstallReport:
    result: Literal['installed', 'unchanged', 'conflict', 'partial', 'failed']
    installed: tuple[str, ...] = ()
    restored: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    backups: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


class _Conflict(ValueError):
    pass


def _info(path: Path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise _Conflict('linked_path')
    return info


def _identity(info):
    return (info.st_dev, info.st_ino) if info else None


class _Directories:
    """Recheck every ancestor and remembered directory identity before filesystem operations."""
    def __init__(self, profile: Path):
        self.profile = profile
        self.identities = {}

    def chain(self, path: Path):
        try:
            relative = path.relative_to(self.profile)
        except ValueError:
            raise _Conflict('unsafe_install_path') from None
        current = self.profile
        yield current
        for part in relative.parts:
            current = current/part
            yield current

    def check(self, path: Path):
        for ancestor in self.chain(path):
            info = _info(ancestor)
            if ancestor in self.identities and _identity(info) != self.identities[ancestor]:
                raise _Conflict('install_parent_changed')
            if info is not None and not stat.S_ISDIR(info.st_mode):
                raise _Conflict('not_a_directory')

    def watch(self, path: Path):
        self.check(path)
        for ancestor in self.chain(path):
            info = _info(ancestor)
            if info is not None:
                self.identities[ancestor] = _identity(info)

    def mkdir(self, path: Path):
        self.check(path)
        path.mkdir(parents=True, exist_ok=True)
        self.watch(path)


@dataclass
class _Action:
    name: str
    target: Path
    old: dict[str, bytes] | None
    backup: Path | None
    published: bool = False


def _tree(path: Path) -> dict[str, bytes] | None:
    info = _info(path)
    if info is None:
        return None
    if not stat.S_ISDIR(info.st_mode):
        raise _Conflict('not_a_directory')
    result = {}
    pending = [path]
    while pending:
        folder = pending.pop()
        for child in sorted(folder.iterdir()):
            info = _info(child)
            if info is None:
                raise _Conflict('tree_changed')
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
            elif stat.S_ISREG(info.st_mode):
                result[child.relative_to(path).as_posix()] = child.read_bytes()
            else:
                raise _Conflict('not_a_regular_file')
    return result


def _relative(key: str) -> bool:
    if not isinstance(key, str) or not key:
        return False
    parts = PurePosixPath(key)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}
    return (not parts.is_absolute() and parts.as_posix() == key and
            all(part not in {'.', '..'} and not part.endswith(('.', ' ')) and
                not any(char in part for char in '\\:*?"<>|') and
                part.split('.')[0].upper() not in reserved for part in parts.parts))


def _hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {key:hashlib.sha256(raw).hexdigest() for key,raw in sorted(files.items())}


def _source_hashes(sources) -> bool:
    return isinstance(sources, dict) and bool(sources) and all(
        _relative(key) and isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value)
        for key,value in sources.items())


def _payloads(bundle: SkillBundle) -> dict[str, dict[str, bytes]]:
    if not _source_hashes(bundle.sources) or not isinstance(bundle.generator_version,str) or not bundle.generator_version:
        raise ValueError('invalid_bundle')
    grouped = {name:{} for name in _NAMES}
    for key,raw in bundle.files.items():
        if not _relative(key) or not isinstance(raw,bytes):
            raise ValueError('invalid_bundle')
        name,sep,relative = key.partition('/')
        if not sep or name not in grouped or not (relative == 'SKILL.md' or relative.startswith('references/') and relative.endswith('.md')):
            raise ValueError('invalid_bundle')
        grouped[name][relative] = raw
    for files in grouped.values():
        if 'SKILL.md' not in files:
            raise ValueError('missing_skill')
        manifest = dict(schema=1, generator_version=bundle.generator_version,
                        sources=bundle.sources, files=_hashes(files))
        files[MANIFEST] = (json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    return grouped


def _managed(files: dict[str, bytes]) -> bool:
    try:
        manifest = json.loads(files.get(MANIFEST, b'').decode('utf-8'))
        actual = {key:raw for key,raw in files.items() if key != MANIFEST}
        return (isinstance(manifest,dict) and set(manifest) == {'schema','generator_version','sources','files'}
                and manifest['schema'] == 1 and isinstance(manifest['generator_version'],str)
                and _source_hashes(manifest['sources']) and isinstance(manifest['files'],dict)
                and all(_relative(key) for key in manifest['files'])
                and manifest['files'] == _hashes(actual) and 'SKILL.md' in actual)
    except (ValueError, UnicodeError, TypeError):
        return False


def _write_tree(path: Path, files: dict[str, bytes], guard: _Directories) -> None:
    guard.check(path.parent)
    path.mkdir(parents=True)
    guard.watch(path)
    for relative,raw in files.items():
        target = path/relative
        guard.mkdir(target.parent)
        with target.open('xb') as stream:
            stream.write(raw)


def _rollback(actions, expected, staging: Path, guard: _Directories):
    restored, conflicts = [], []
    for action in reversed(actions):
        name,target,old,backup = action.name,action.target,action.old,action.backup
        try:
            guard.check(target.parent)
            if backup:
                guard.check(backup.parent)
            current = _tree(target)
            saved = _tree(backup) if backup else None
            if action.published and current is None:
                conflicts.append(name)  # The author removed/moved an already published directory.
                continue
            if current == old:
                continue
            if old is not None and saved != old:
                conflicts.append(name)
                continue
            if current is not None:
                if current != expected[name]:
                    conflicts.append(name)
                    continue
                rescue = staging/'rollback'/name
                guard.mkdir(rescue.parent)
                guard.check(target.parent)
                os.replace(target,rescue)
            if old is not None:
                guard.check(backup.parent)
                guard.check(target.parent)
                os.replace(backup,target)
            restored.append(name)
        except (OSError,_Conflict):
            conflicts.append(name)
    return tuple(restored),tuple(conflicts)


def _available_backups(backups: list[Path], guard: _Directories) -> tuple[Path, ...]:
    available = []
    for path in backups:
        try:
            guard.check(path.parent)
            if _info(path):
                available.append(path)
        except (OSError,_Conflict):
            pass
    return tuple(available)


def install_skills(bundle: SkillBundle, userprofile: Path) -> InstallReport:
    try:
        expected = _payloads(bundle)
    except (ValueError,TypeError,AttributeError):
        return InstallReport('failed',errors=('invalid_bundle',))
    profile = Path(userprofile)
    if not profile.is_absolute():
        return InstallReport('failed',errors=('profile_must_be_absolute',))
    agents = profile/'.agents'
    skills = agents/'skills'
    backup_root, staging_root = agents/'obscura-backups',agents/'obscura-staging'
    guard = _Directories(profile)
    try:
        for path in (profile,agents,skills,backup_root,staging_root):
            guard.watch(path)
    except _Conflict:
        return InstallReport('conflict',errors=('unsafe_install_root',))
    except OSError:
        return InstallReport('failed',errors=('install_access_denied',))
    lock = agents/'.obscura-install.lock'
    try:
        guard.mkdir(agents)
        lock.mkdir()
        lock_identity = _identity(_info(lock))
    except FileExistsError:
        return InstallReport('conflict',errors=('install_busy',))
    except _Conflict:
        return InstallReport('conflict',errors=('install_parent_changed',))
    except OSError:
        return InstallReport('failed',errors=('install_access_denied',))
    actions, backups = [], []
    staging = staging_root/uuid.uuid4().hex
    try:
        originals, conflicts = {}, []
        for name in _NAMES:
            try:
                guard.check(skills)
                old = _tree(skills/name)
                originals[name] = old
                if old is not None and not _managed(old):
                    conflicts.append(name)
            except _Conflict:
                conflicts.append(name)
        if conflicts:
            return InstallReport('conflict',conflicts=tuple(conflicts))
        changed = [name for name in _NAMES if originals[name] != expected[name]]
        if not changed:
            return InstallReport('unchanged')
        guard.mkdir(staging)
        for name in _NAMES:
            _write_tree(staging/name,expected[name],guard)
        backup_dir = backup_root/staging.name
        for name in changed:
            target = skills/name
            old = originals[name]
            guard.check(target.parent)
            guard.check(staging)
            guard.check(backup_root)
            if _tree(target) != old:
                raise _Conflict(name)
            guard.mkdir(target.parent)
            backup = backup_dir/name if old is not None else None
            action = _Action(name,target,old,backup)
            actions.append(action)
            if backup:
                guard.mkdir(backup.parent)
                guard.check(target.parent)
                os.replace(target,backup)
                backups.append(backup)
            guard.check(staging)
            guard.check(target.parent)
            os.replace(staging/name,target)
            action.published = True
        for name in _NAMES:
            guard.check(skills)
            if _tree(skills/name) != expected[name]:
                raise _Conflict(name)
        return InstallReport('installed',installed=tuple(changed),backups=tuple(backups))
    except (OSError,_Conflict) as error:
        restored, rollback_conflicts = _rollback(actions,expected,staging,guard)
        initial = (str(error),) if isinstance(error,_Conflict) else ()
        conflicts = tuple(dict.fromkeys((*initial,*rollback_conflicts)))
        installed = []
        for action in actions:
            try:
                guard.check(action.target.parent)
                if _tree(action.target) == expected[action.name]:
                    installed.append(action.name)
            except (OSError,_Conflict):
                pass
        result = 'partial' if rollback_conflicts else 'conflict' if initial else 'failed'
        return InstallReport(result,installed=tuple(installed),restored=restored,conflicts=conflicts,
                             backups=_available_backups(backups,guard),
                             errors=('install_changed' if initial else 'install_io_failed',))
    finally:
        try:
            guard.check(agents)
            if _identity(_info(lock)) == lock_identity:
                lock.rmdir()
        except (OSError,_Conflict):
            pass
