"""SQLite (local) or Neon Postgres (DATABASE_URL) for Cheongyang Plus."""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("CYPLUS_DATABASE", str(ROOT / "data" / "cheongyangplus.db")))
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("CYPLUS_DATABASE_URL") or ""

IGNORE_CONFLICT = {
    "module_registry": "(slug)",
    "settings": "(key)",
}

DB_LOCK = threading.Lock()


def backend_name() -> str:
    return "postgres" if DATABASE_URL else "sqlite"


def use_postgres() -> bool:
    return bool(DATABASE_URL)


def _adapt_sql(sql: str) -> str:
    if not use_postgres():
        return sql
    out = sql
    m = re.search(r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)", out, re.I)
    if m:
        table = m.group(1).lower()
        out = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", out, flags=re.I)
        target = IGNORE_CONFLICT.get(table)
        if target and "ON CONFLICT" not in out.upper():
            out = out.rstrip().rstrip(";") + f" ON CONFLICT {target} DO NOTHING"
    out = out.replace("?", "%s")
    out = re.sub(r"\bINTEGER PRIMARY KEY\b", "SERIAL PRIMARY KEY", out, flags=re.I)
    out = out.replace("AUTOINCREMENT", "")
    return out


class _PgRow(Mapping):
    __slots__ = ("_names", "_values")

    def __init__(self, names, values):
        self._names = names
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            val = self._values[key]
        else:
            val = self._values[self._names.index(key)]
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return val

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)


class _PgCursor:
    def __init__(self, cur, names):
        self._cur = cur
        self._names = names or []
        self.lastrowid = None

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if self._names == ["id"] and len(row) == 1:
            self.lastrowid = row[0]
        return _PgRow(self._names, row)

    def fetchall(self):
        return [_PgRow(self._names, r) for r in self._cur.fetchall()]


class _PgCompat:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        adapted = _adapt_sql(sql)
        cur.execute(adapted, params or ())
        names = [d[0] for d in (cur.description or [])]
        return _PgCursor(cur, names)

    def executescript(self, script: str):
        for stmt in filter(None, (s.strip() for s in script.split(";"))):
            if not stmt or stmt.startswith("--"):
                continue
            upper = stmt.upper()
            if upper.startswith("PRAGMA"):
                continue
            self.execute(stmt + ";")

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(_adapt_sql(sql), seq_of_params)
        return cur


class _SqliteCompat:
    def __init__(self, con):
        self._con = con

    def execute(self, sql, params=()):
        return self._con.execute(sql, params)

    def executescript(self, script: str):
        self._con.executescript(script)

    def executemany(self, sql, seq_of_params):
        return self._con.executemany(sql, seq_of_params)


@contextmanager
def db_connect():
    if use_postgres():
        import ssl
        from urllib.parse import urlparse

        import pg8000.dbapi

        u = urlparse(DATABASE_URL)
        conn = pg8000.dbapi.connect(
            user=u.username,
            password=u.password,
            host=u.hostname,
            port=u.port or 5432,
            database=u.path.lstrip("/"),
            ssl_context=ssl.create_default_context(),
        )
        wrapper = _PgCompat(conn)
        try:
            yield wrapper
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_PATH, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        wrapper = _SqliteCompat(con)
        try:
            with con:
                yield wrapper
        finally:
            con.close()


def table_columns(db, table: str) -> set[str]:
    if use_postgres():
        cur = db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
            (table.lower(),),
        )
        return {r[0] for r in cur.fetchall()}
    cur = db.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}
