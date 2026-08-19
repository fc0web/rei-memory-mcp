"""SQLite connection and schema management for rei-memory-mcp.

FTS5 with the ``trigram`` tokenizer is used for Japanese full-text search;
the default ``unicode61`` tokenizer does not segment Japanese and would make
search silently useless.

Schema is idempotent — ``init_schema`` can be called on an existing DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS theories (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    tier          TEXT NOT NULL CHECK (tier IN ('proven', 'hypothesis', 'speculative')),
    step          INTEGER,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    source        TEXT,
    immutable     INTEGER NOT NULL DEFAULT 0 CHECK (immutable IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_theories_tier ON theories(tier);
CREATE INDEX IF NOT EXISTS idx_theories_step ON theories(step);

CREATE TABLE IF NOT EXISTS theory_links (
    from_id  TEXT NOT NULL,
    to_id    TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('depends', 'contradicts', 'generalizes', 'related')),
    PRIMARY KEY (from_id, to_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_links_from ON theory_links(from_id, kind);
CREATE INDEX IF NOT EXISTS idx_links_to   ON theory_links(to_id, kind);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS theories_fts USING fts5(
    id UNINDEXED,
    title,
    body,
    tokenize = 'trigram'
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults.

    Uses row_factory=Row for dict-like access; enables foreign keys
    (harmless — no FKs currently, but future-proof).
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and FTS5 virtual table if not present. Idempotent."""
    conn.executescript(SCHEMA_SQL)
    conn.execute(FTS_SQL)
    conn.commit()


def open_db(db_path: str | Path) -> sqlite3.Connection:
    """Convenience: connect + init schema in one call."""
    conn = connect(db_path)
    init_schema(conn)
    return conn
