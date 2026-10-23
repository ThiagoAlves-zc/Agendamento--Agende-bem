"""Conexão e inicialização do banco SQLite local."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "agende_bem.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS professionals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    specialty  TEXT    NOT NULL DEFAULT '',
    day_start  TEXT    NOT NULL DEFAULT '08:00',
    day_end    TEXT    NOT NULL DEFAULT '18:00',
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name     TEXT    NOT NULL,
    professional_id  INTEGER NOT NULL REFERENCES professionals(id),
    day              TEXT    NOT NULL,
    start_time       TEXT    NOT NULL,
    duration_min     INTEGER NOT NULL CHECK (duration_min > 0),
    status           TEXT    NOT NULL DEFAULT 'confirmado'
                     CHECK (status IN ('confirmado', 'cancelado')),
    origin           TEXT    NOT NULL DEFAULT 'agenda'
                     CHECK (origin IN ('agenda', 'encaixe')),
    replaces_id      INTEGER REFERENCES appointments(id),
    waiting_id       INTEGER REFERENCES waiting_list(id),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    cancelled_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_appointments_day ON appointments(day, professional_id);

CREATE TABLE IF NOT EXISTS waiting_list (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name     TEXT    NOT NULL,
    professional_ids TEXT    NOT NULL,
    duration_min     INTEGER NOT NULL CHECK (duration_min > 0),
    available_from   TEXT    NOT NULL,
    available_until  TEXT    NOT NULL,
    requested_on     TEXT    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'ativo'
                     CHECK (status IN ('ativo', 'encaixado', 'removido')),
    notes            TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    event_type  TEXT    NOT NULL,
    entity      TEXT    NOT NULL,
    entity_id   INTEGER,
    details     TEXT    NOT NULL DEFAULT ''
);
"""


def db_path() -> Path:
    """Caminho do banco; pode ser sobrescrito por AGENDE_BEM_DB."""
    return Path(os.environ.get("AGENDE_BEM_DB", DEFAULT_DB_PATH))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transação explícita com bloqueio de escrita imediato (BEGIN IMMEDIATE)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
