import hashlib

import pytest

import file_library
from authorization import AccessDenied, Actor, Role
from file_library import FileLibraryError, archive_asset, download_asset, list_assets, upload_asset
from template_catalog import default_templates, register_defaults


class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def upload(self, bucket, key, content, mime_type):
        self.objects[(bucket, key)] = (content, mime_type)

    def download(self, bucket, key):
        return self.objects[(bucket, key)][0]

    def delete(self, bucket, key):
        self.deleted.append((bucket, key))
        self.objects.pop((bucket, key), None)


ADMIN = Actor("00000000-0000-0000-0000-000000000010", "admin@example.test", Role.ADMIN)
READ = Actor("00000000-0000-0000-0000-000000000011", "read@example.test", Role.READ)
CSV = b"data;horario;duracao_min;profissional;especialidade;paciente;status\n2026-01-01;08:00;30;Dra;Clinica;Exemplo;confirmado\n"


def test_upload_download_and_archive_require_permissions(conn):
    storage = MemoryStorage()
    asset = upload_asset(conn, storage, ADMIN, "agenda.csv", CSV, "text/csv")
    assert asset.sha256 == hashlib.sha256(CSV).hexdigest()
    assert list_assets(conn, ADMIN)[0].id == asset.id

    downloaded, content = download_asset(conn, storage, READ, asset.id)
    assert downloaded.id == asset.id
    assert content == CSV

    with pytest.raises(AccessDenied):
        upload_asset(conn, storage, READ, "nao.csv", CSV, "text/csv")
    with pytest.raises(AccessDenied):
        archive_asset(conn, READ, asset.id)

    archive_asset(conn, ADMIN, asset.id)
    assert list_assets(conn, ADMIN) == []
    with pytest.raises(FileLibraryError):
        download_asset(conn, storage, READ, asset.id)


def test_download_detects_integrity_failure(conn):
    storage = MemoryStorage()
    asset = upload_asset(conn, storage, ADMIN, "agenda.csv", CSV, "text/csv")
    storage.objects[(asset.storage_bucket, asset.storage_object_key)] = (b"alterado", "text/csv")
    with pytest.raises(FileLibraryError, match="integridade"):
        download_asset(conn, storage, READ, asset.id)


def test_failed_metadata_write_compensates_uploaded_storage(conn, monkeypatch):
    storage = MemoryStorage()

    def fail_insert(*args, **kwargs):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(file_library, "_insert", fail_insert)
    with pytest.raises(RuntimeError, match="banco indisponível"):
        upload_asset(conn, storage, ADMIN, "agenda.csv", CSV, "text/csv")
    assert storage.objects == {}
    assert len(storage.deleted) == 1


def test_default_templates_are_real_and_registration_is_idempotent(conn):
    storage = MemoryStorage()
    seeds = default_templates()
    assert len(seeds) == 5
    assert all(seed.content for seed in seeds)
    assert next(seed for seed in seeds if seed.template_type == "pdf").content.startswith(b"%PDF-")

    assert register_defaults(conn, storage, ADMIN) == 5
    assert register_defaults(conn, storage, ADMIN) == 0
    assert conn.execute("SELECT count(*) AS n FROM file_templates").fetchone()["n"] == 5
    assert conn.execute("SELECT count(*) AS n FROM file_template_versions").fetchone()["n"] == 5
