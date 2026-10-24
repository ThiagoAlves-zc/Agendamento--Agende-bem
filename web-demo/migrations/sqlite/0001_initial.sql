-- 0001 (SQLite): esquema inicial do Agende Bem (equivalente ao MVP aceaec9).
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
