-- 0002 (SQLite): equivalente local da fundação V3.
-- O conteúdo dos arquivos não é armazenado no SQLite; apenas metadados são testados aqui.

CREATE TABLE IF NOT EXISTS patients (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    status       TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_patients_status ON patients (status);

CREATE TABLE IF NOT EXISTS file_assets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name      TEXT NOT NULL,
    display_name       TEXT NOT NULL,
    file_extension     TEXT NOT NULL,
    mime_type          TEXT NOT NULL CHECK (mime_type IN ('text/csv', 'application/pdf')),
    byte_size          INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 5242880),
    storage_bucket     TEXT NOT NULL,
    storage_object_key TEXT NOT NULL,
    sha256             TEXT NOT NULL,
    category           TEXT NOT NULL CHECK (category IN ('operacional', 'modelo')),
    status             TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'arquivado')),
    created_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (storage_bucket, storage_object_key)
);
CREATE INDEX IF NOT EXISTS idx_file_assets_category_status ON file_assets (category, status, created_at DESC);

CREATE TABLE IF NOT EXISTS file_templates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL UNIQUE,
    description      TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL CHECK (category IN ('agenda', 'lista_espera', 'profissionais', 'guia', 'relatorio')),
    template_type    TEXT NOT NULL CHECK (template_type IN ('csv', 'pdf')),
    current_asset_id INTEGER NOT NULL REFERENCES file_assets(id),
    current_version  INTEGER NOT NULL DEFAULT 1 CHECK (current_version > 0),
    status           TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'arquivado')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS file_template_versions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id    INTEGER NOT NULL REFERENCES file_templates(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    asset_id       INTEGER NOT NULL REFERENCES file_assets(id),
    change_summary TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (template_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_file_template_versions_template
    ON file_template_versions (template_id, version_number DESC);
