"""Read-only SQLite access for the serving API.

One connection per request is cheap with SQLite; WAL lets readers run while the
ETL writer finishes. Every query is parameterised.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def db_path() -> Path:
    return Path(settings.db_path)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=1")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


@contextmanager
def connection():
    """Read-only connection (guarded by PRAGMA query_only)."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write_connection():
    """Writable connection for the simulator / events. WAL keeps readers unblocked."""
    conn = sqlite3.connect(db_path(), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    with connection() as conn:
        return conn.execute(sql, params).fetchall()


def one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    with connection() as conn:
        return conn.execute(sql, params).fetchone()


def scalar(sql: str, params: tuple | dict = ()):
    row = one(sql, params)
    return row[0] if row else None


def is_ready() -> bool:
    p = db_path()
    if not p.exists():
        return False
    try:
        return scalar("SELECT COUNT(*) FROM shops") is not None
    except sqlite3.Error:
        return False


def counts() -> dict:
    out = {}
    for table in ("shops", "products", "offers", "malls", "neighbourhoods"):
        try:
            out[table] = scalar(f"SELECT COUNT(*) FROM {table}")
        except sqlite3.Error:
            out[table] = None
    return out


def meta() -> dict:
    import json

    try:
        row = one("SELECT value FROM meta WHERE key='build'")
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}
