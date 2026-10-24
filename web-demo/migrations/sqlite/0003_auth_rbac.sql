-- 0003 (SQLite): equivalente local dos papéis operacionais.
CREATE TABLE IF NOT EXISTS app_users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('administrador', 'recepcao', 'leitura')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
