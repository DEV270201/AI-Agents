"""SQLite access for the expense tracker database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DB_PATH = _DATA_DIR / "expenser.db"
_SCHEMA_PATH = _DATA_DIR / "expense_schema.sql"


def _apply_schema_if_needed(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='expenses' LIMIT 1"
    ).fetchone()
    if row is not None:
        return
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def init_db() -> None:
    """Create the data directory and database file, and apply ``expense_schema.sql`` when tables are missing."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    try:
        _apply_schema_if_needed(conn)
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to ``data/expenser.db``.

    Call ``init_db()`` once before first use so tables exist.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(_DB_PATH)
