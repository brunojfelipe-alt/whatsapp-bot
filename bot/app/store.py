"""Persistência SQLite de contatos e mensagens."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    jid TEXT PRIMARY KEY,
    name TEXT,
    state TEXT NOT NULL DEFAULT 'menu',
    fallback_count INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jid TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    text TEXT NOT NULL,
    ts REAL NOT NULL
);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class Store:
    """Camada de acesso a dados. Uma instância por caminho de banco (facilita testes)."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = _connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_contact(self, jid: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM contacts WHERE jid = ?", (jid,)).fetchone()

    def upsert_contact(self, jid: str, name: str | None = None, state: str | None = None,
                        fallback_count: int | None = None) -> sqlite3.Row:
        existing = self.get_contact(jid)
        now = time.time()
        with self._conn() as conn:
            if existing is None:
                conn.execute(
                    "INSERT INTO contacts (jid, name, state, fallback_count, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (jid, name, state or "menu", fallback_count or 0, now),
                )
            else:
                new_name = name if name is not None else existing["name"]
                new_state = state if state is not None else existing["state"]
                new_fallback = fallback_count if fallback_count is not None else existing["fallback_count"]
                conn.execute(
                    "UPDATE contacts SET name = ?, state = ?, fallback_count = ?, updated_at = ? "
                    "WHERE jid = ?",
                    (new_name, new_state, new_fallback, now, jid),
                )
        return self.get_contact(jid)

    def add_message(self, jid: str, direction: str, text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (jid, direction, text, ts) VALUES (?, ?, ?, ?)",
                (jid, direction, text, time.time()),
            )

    def last_messages(self, jid: str, limit: int = 5) -> list[sqlite3.Row]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE jid = ? ORDER BY ts DESC LIMIT ?",
                (jid, limit),
            ).fetchall()
        return list(reversed(rows))

    def list_conversations(self, limit: int = 50) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM contacts ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
