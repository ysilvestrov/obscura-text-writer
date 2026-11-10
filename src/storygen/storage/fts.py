"""In-memory FTS5 ranking for memory selection (#60): a throwaway index per call, never the story database."""
import sqlite3


def bm25_rank(bodies: list[str], terms: list[str]) -> list[tuple[int,float]]:
    """(index, bm25) of bodies matching any term in a trigram FTS5 index; bodies and terms are already normalised."""
    if not bodies or not terms:return []
    db=sqlite3.connect(':memory:')
    try:
        db.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='trigram')")
        db.executemany('INSERT INTO t(rowid, body) VALUES (?, ?)',list(enumerate(bodies)))
        return db.execute('SELECT rowid, bm25(t) FROM t WHERE t MATCH ?',(' OR '.join(f'"{t}"' for t in terms),)).fetchall()
    finally:
        db.close()
