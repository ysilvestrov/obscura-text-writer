"""Read-only catalog diagnostics; never instantiate the migrating Repository."""
import hashlib
import json
import sqlite3
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..domain import Scene, Story, VersionRef


@dataclass
class IntegrityIssue:
    code: str
    path: str
    message: str


@dataclass
class IntegrityReport:
    issues: list[IntegrityIssue] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    versions_checked: int = 0
    sources_checked: int = 0
    auxiliary_files: int = 0

    @property
    def ok(self):
        return not self.issues

    def to_dict(self):
        return {'ok': self.ok, **asdict(self)}

    def add(self, code, path, message):
        self.issues.append(IntegrityIssue(code, str(path), message))


def contained_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if not relative or path.is_absolute() or '..' in path.parts or path.drive or ':' in relative:
        raise ValueError('Небезпечний відносний шлях')
    candidate = root / path
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('Шлях поза каталогом')
    for part in [candidate, *candidate.parents]:
        if part == root:
            break
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('Посилання/reparse point не підтримується')
    return candidate


def regular_files(root: Path) -> list[Path]:
    result = []
    def visit(directory):
        for path in directory.iterdir():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('Посилання/reparse point не підтримується')
            if stat.S_ISDIR(info.st_mode):
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                result.append(path)
            else:
                raise ValueError('Неочікуваний тип файла')
    visit(root)
    return sorted(result)


def readonly_database(path: Path):
    # A closed, checkpointed WAL database otherwise creates SHM/WAL on a read.
    wal = path.with_name(path.name + '-wal')
    immutable = '&immutable=1' if not wal.exists() or wal.stat().st_size == 0 else ''
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro' + immutable, uri=True, timeout=5)


def check_integrity(root: Path) -> IntegrityReport:
    root = Path(root).resolve()
    report = IntegrityReport()
    database = root / 'storygen.sqlite3'
    if not database.is_file():
        report.add('database_missing', 'storygen.sqlite3', 'База даних відсутня')
        return report
    try:
        files = regular_files(root)
    except (OSError, ValueError):
        report.add('unsafe_path', '.', 'Небезпечне або недоступне дерево файлів')
        return report
    tracked = set()

    def verify_file(relative, digest):
        try:
            path = contained_path(root, relative)
            tracked.add(path)
            if not path.is_file():
                report.add('file_missing', relative, 'Файл відсутній')
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                report.add('hash_mismatch', relative, 'SHA-256 не відповідає каталогу')
        except ValueError:
            report.add('unsafe_path', relative, 'Шлях поза каталогом або посилання')
        except OSError:
            report.add('file_unreadable', relative, 'Файл недоступний')

    try:
        db = readonly_database(database)
        try:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if db.execute('PRAGMA user_version').fetchone()[0] != 2:
                report.add('unsupported_schema', 'storygen.sqlite3', 'Підтримується лише схема 2; міграції не виконуються')
                return report
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                report.add('sqlite_integrity', 'storygen.sqlite3', 'SQLite integrity_check виявив помилки')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                report.add('foreign_key', 'storygen.sqlite3', 'Порушено SQL foreign key')
            stories, scenes, versions = {}, {}, {}
            for table, model, result, columns in [
                ('stories', Story, stories, ['id']),
                ('scenes', Scene, scenes, ['id', 'story_id', 'position']),
                ('versions', VersionRef, versions, ['id', 'story_id', 'scene_id', 'kind']),
            ]:
                for row in db.execute(f'SELECT {",".join(columns)},payload FROM {table}'):
                    try:
                        item = model.model_validate_json(row[-1])
                        result[row[0]] = item
                        if any(getattr(item, column) != value for column, value in zip(columns, row[:-1])):
                            report.add('payload_mismatch', row[0], 'Payload не відповідає SQL-колонкам')
                    except ValueError:
                        report.add('invalid_payload', row[0], 'Некоректний доменний payload')
            from .memory_checks import check_memory_versions
            check_memory_versions(report,root,versions)
            from .character_checks import check_character_versions
            check_character_versions(report,root,versions,scenes,stories)
            edges = set(db.execute('SELECT source_id,target_id FROM dependency_edges'))
            expected_edges = set()
            for ref in versions.values():
                report.versions_checked += 1
                verify_file(ref.relative_path, ref.sha256)
                if ref.story_id not in stories or (ref.scene_id and (ref.scene_id not in scenes or scenes[ref.scene_id].story_id != ref.story_id)):
                    report.add('invalid_owner', ref.id, 'Невірний власник версії')
                if ref.dependency_snapshot is not None:
                    snapshot=ref.dependency_snapshot
                    invalid=any(id not in versions or versions[id].story_id!=ref.story_id or versions[id].sha256!=sha for id,sha in snapshot.refs.items())
                    invalid=invalid or snapshot.scope!='author_text' and set(snapshot.refs)!=set(ref.input_refs)
                    invalid=invalid or len(snapshot.scene_order)!=len(set(snapshot.scene_order)) or any(id not in scenes or scenes[id].story_id!=ref.story_id for id in snapshot.scene_order)
                    invalid=invalid or not set(snapshot.ref_baselines)<=set(snapshot.refs)
                    for selector in snapshot.selectors:
                        if selector.kind in {'scene','head'} or selector.kind=='order' and selector.field=='prefix':
                            invalid=invalid or selector.owner_id not in scenes or scenes[selector.owner_id].story_id!=ref.story_id
                        else:
                            invalid=invalid or selector.owner_id!=ref.story_id
                    if invalid:
                        report.add('invalid_snapshot',ref.id,'Невірна власність або хеш залежностей знімка')
                for source in ref.input_refs:
                    expected_edges.add((source, ref.id))
                    if source not in versions or versions[source].story_id != ref.story_id:
                        report.add('invalid_source', ref.id, 'Невірне джерело залежності')
            from ..dependency_models import AcceptanceRecord
            decisions={}
            for key,payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'acceptance:%' ORDER BY rowid"):
                try:
                    record=AcceptanceRecord.model_validate_json(payload)
                    ref=versions.get(record.version_id)
                    invalid=key!='acceptance:'+record.story_id+':'+record.id or not ref or ref.story_id!=record.story_id or ref.scene_id!=record.scene_id or ref.kind not in {'draft','edited','manual'} or record.baseline.scope!='author_text'
                    invalid=invalid or record.action!=('accept_draft' if ref and ref.kind=='draft' else 'accept_prose')
                    prior=decisions.get(record.previous_baseline_id)
                    invalid=invalid or record.previous_baseline_id is not None and record.previous_baseline_id!=record.version_id and (not prior or prior.version_id!=record.version_id)
                    for id,sha in record.baseline.refs.items():
                        invalid=invalid or id not in versions or versions[id].story_id!=record.story_id or versions[id].sha256!=sha
                    for selector in record.baseline.selectors:
                        if selector.kind in {'scene','head'} or selector.kind=='order' and selector.field=='prefix':
                            invalid=invalid or selector.owner_id not in scenes or scenes[selector.owner_id].story_id!=record.story_id
                        else:invalid=invalid or selector.owner_id!=record.story_id
                    invalid=invalid or any(id not in scenes or scenes[id].story_id!=record.story_id for id in record.baseline.scene_order)
                    invalid=invalid or len(record.baseline.scene_order)!=len(set(record.baseline.scene_order)) or not set(record.baseline.ref_baselines)<=set(record.baseline.refs)
                    for id,baseline in record.baseline.ref_baselines.items():
                        invalid=invalid or baseline is not None and (baseline not in decisions or decisions[baseline].version_id!=id)
                    if invalid:raise ValueError('Некоректний запис')
                    decisions[record.id]=record
                except (ValueError,TypeError):
                    report.add('invalid_acceptance',key,'Некоректний формат або власність рішення автора')
            for ref in versions.values():
                if ref.dependency_snapshot:
                    for id,baseline in ref.dependency_snapshot.ref_baselines.items():
                        if baseline and (baseline not in decisions or decisions[baseline].version_id!=id):
                            report.add('invalid_snapshot',ref.id,'Невірне посилання на baseline джерела')
            if edges != expected_edges:
                report.add('dependency_mismatch', 'dependency_edges', 'Граф не відповідає input_refs')
            allowed = {'plan': {'scene_plan'}, 'brief': {'brief'}, 'draft': {'draft'}, 'prose': {'edited', 'manual'}, 'memory': {'memory'}}
            for scene in scenes.values():
                for head, version_id in scene.heads.items():
                    ref = versions.get(version_id)
                    if not ref or ref.scene_id != scene.id or ref.story_id != scene.story_id or ref.kind not in allowed.get(head, set()) or not ref.complete:
                        report.add('invalid_head', scene.id, 'Невірна головна версія сцени')
            for story in stories.values():
                for attr, kind in [('canon_version_id', 'canon'), ('style_version_id', 'style'), ('characters_version_id', 'character_cards')]:
                    version_id = getattr(story, attr)
                    ref = versions.get(version_id)
                    if version_id and (not ref or ref.story_id != story.id or ref.scene_id is not None or ref.kind != kind):
                        report.add('invalid_head', story.id, 'Невірний матеріал твору')
            for story_id, payload in db.execute('SELECT story_id,payload FROM source_files'):
                try:
                    source = json.loads(payload)
                    report.sources_checked += 1
                    verify_file(source['relative_path'], source['sha256'])
                    ref = versions.get(source['version_id'])
                    if not ref or ref.story_id != story_id or ref.kind != source['kind']:
                        report.add('invalid_source', source.get('id', story_id), 'Невірний імпортований матеріал')
                except (ValueError, KeyError, TypeError):
                    report.add('invalid_payload', story_id, 'Некоректні метадані джерела')
        finally:
            db.close()
    except sqlite3.Error:
        report.add('database_error', 'storygen.sqlite3', 'Не вдалося прочитати каталог SQLite')
        return report
    for path in files:
        relative = path.relative_to(root)
        if path in tracked or relative.as_posix() in {'storygen.sqlite3', 'storygen.sqlite3-wal', 'storygen.sqlite3-shm', 'storygen.sqlite3-journal', 'worker.lock'}:
            continue
        if len(relative.parts) >= 4 and relative.parts[0] == 'stories' and relative.parts[2] in {'versions', 'sources'}:
            report.add('orphan_blob', relative, 'Immutable файл не зареєстрований у каталозі')
        else:
            report.auxiliary_files += 1
    return report
