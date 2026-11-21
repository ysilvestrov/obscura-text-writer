"""PERF-001-S06 guards: every write the shared snapshot must see goes through Database.connection() of this process,
except token profiles, which storygen-tokens writes from another process and every request reads again."""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from tests.storage.test_freshness import setup

SRC = Path(__file__).resolve().parents[2] / 'src' / 'storygen'


def _files_matching(pattern):
    return sorted(p.relative_to(SRC).as_posix() for p in SRC.rglob('*.py') if re.search(pattern, p.read_text(encoding='utf-8')))


def test_only_allowed_modules_open_sqlite():
    allowed = {'storage/database.py', 'storage/backup.py', 'storage/integrity.py', 'storage/pre_migration.py', 'storage/fts.py'}
    assert set(_files_matching(r'sqlite3\.connect\(')) <= allowed


def test_no_commit_outside_the_connection_exit():
    # Database.connection() commits on exit; migrations in Database.__init__ commit inside executescript.
    assert _files_matching(r"\.commit\(\)|['\"]COMMIT['\"]") == []
    assert _files_matching(r'COMMIT;') == ['storage/database.py']


def test_clis_take_the_lock_or_write_only_token_profiles():
    for path in SRC.glob('*/cli.py'):
        text = path.read_text(encoding='utf-8')
        if 'Repository(' not in text:
            continue
        name = path.relative_to(SRC).as_posix()
        assert 'AppInstanceLock' in text or name == 'token_budget/cli.py', name


def test_token_profiles_written_by_another_process_are_seen(tmp_path):
    repo, story, scene, draft, prose = setup(tmp_path)
    assert repo.context_view(story.id).token_records('profile') == []
    # Another process (storygen-tokens) writes without this process's connection(): no generation change.
    with closing(sqlite3.connect(repo.db.path)) as db, db:
        db.execute("INSERT INTO app_settings(key,payload) VALUES('token_profile:x', ?)", (json.dumps({'id': 'x'}),))
    assert repo.context_view(story.id).token_records('profile') == [{'id': 'x'}]
