"""PERF-001-S06: the data generation of a database (#39, part 2)."""
import threading

import pytest

from storygen.storage.database import Database


def _insert(c, key):
    c.execute("INSERT INTO app_settings(key,payload) VALUES(?, '{}')", (key,))


def test_read_and_empty_rollback_keep_generation(tmp_path):
    db = Database(tmp_path / 'x.sqlite3')
    start = db.generation()
    with db.connection() as c:
        c.execute('SELECT 1').fetchone()
    with pytest.raises(RuntimeError), db.connection():
        raise RuntimeError
    assert db.generation() == start


def test_writing_commit_and_writing_rollback_each_add_two(tmp_path):
    db = Database(tmp_path / 'x.sqlite3')
    start = db.generation()
    with db.connection() as c:
        _insert(c, 'a')
    assert db.generation() == start + 2
    with pytest.raises(RuntimeError), db.connection() as c:
        _insert(c, 'b')
        raise RuntimeError
    assert db.generation() == start + 4
    with db.connection() as c:
        assert c.execute("SELECT count(*) FROM app_settings WHERE key='b'").fetchone()[0] == 0


def test_connection_remembers_state_at_open(tmp_path):
    db = Database(tmp_path / 'x.sqlite3')
    with db.connection() as c:
        assert db.opened_state(c) == (db.generation(), 0)


def test_connection_opened_during_a_commit_sees_it_in_flight(tmp_path):
    db = Database(tmp_path / 'x.sqlite3')
    seen = {}
    before = db.generation()
    inside, release = threading.Event(), threading.Event()

    def writer():
        with db.connection() as c:
            _insert(c, 'a')
            # Test hook: runs after the generation is marked in flight and before the commit.
            db._before_commit_hook = lambda: (inside.set(), release.wait(5))
    thread = threading.Thread(target=writer)
    thread.start()
    assert inside.wait(5)
    with db.connection() as c:
        seen['state'] = db.opened_state(c)
    release.set()
    thread.join(5)
    db._before_commit_hook = None
    assert seen['state'] == (before + 1, 1)


def test_two_databases_on_one_path_share_generation(tmp_path):
    a = Database(tmp_path / 'x.sqlite3')
    b = Database(tmp_path / 'x.sqlite3')
    before = a.generation()
    with b.connection() as c:
        _insert(c, 'a')
    assert a.generation() == b.generation() == before + 2


def test_bump_generation_for_writes_outside_connection(tmp_path):
    db = Database(tmp_path / 'x.sqlite3')
    before = db.generation()
    db.bump_generation()
    assert db.generation() == before + 2
