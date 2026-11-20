import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path):
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                feed TEXT NOT NULL,
                publisher TEXT NOT NULL,
                author TEXT NOT NULL,
                language TEXT NOT NULL,
                published_at TEXT NOT NULL,
                headline TEXT NOT NULL,
                url TEXT NOT NULL,
                body TEXT NOT NULL,
                categories TEXT NOT NULL,
                tickers TEXT NOT NULL,
                edition_id TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS article_edition ON articles(edition_id);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS briefings (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audio (
                briefing_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                provider TEXT NOT NULL
            );
        """)
