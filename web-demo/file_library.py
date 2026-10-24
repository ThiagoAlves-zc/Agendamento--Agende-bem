"""Biblioteca operacional: conteúdo no Storage, metadados privados no PostgreSQL."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Protocol

import requests

from authorization import Actor, Permission, require
from database import Database, transaction
from file_validation import ValidatedOperationalFile, validate_operational_file
from services import _insert, log_event

BUCKET = "agende-bem-operacional"


class FileLibraryError(RuntimeError):
    pass


class Storage(Protocol):
    def upload(self, bucket: str, key: str, content: bytes, mime_type: str) -> None: ...
    def download(self, bucket: str, key: str) -> bytes: ...
    def delete(self, bucket: str, key: str) -> None: ...


class SupabaseStorage:
    """Cliente servidor da API oficial de Storage; a chave secreta nunca vai ao browser."""
    def __init__(self, url: str | None = None, secret_key: str | None = None, http=None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.secret_key = secret_key or os.environ.get("SUPABASE_SECRET_KEY", "")
        self.http = http or requests.Session()

    def _headers(self, mime: str | None = None) -> dict[str, str]:
        if not self.url.startswith("https://") or not self.secret_key:
            raise FileLibraryError("Storage não está configurado neste ambiente.")
        h = {"apikey": self.secret_key, "Authorization": f"Bearer {self.secret_key}"}
        if mime:
            h["Content-Type"] = mime
        return h

    def _request(self, method: str, path: str, *, content: bytes | None = None,
                 mime: str | None = None, json_payload: dict | None = None):
        try:
            response = self.http.request(
                method, self.url + path, headers=self._headers(mime), data=content,
                json=json_payload, timeout=20,
            )
        except requests.RequestException as exc:
            raise FileLibraryError("Falha ao comunicar com o Storage.") from exc
        if response.status_code >= 400:
            raise FileLibraryError("O Storage recusou a operação solicitada.")
        return response

    def upload(self, bucket: str, key: str, content: bytes, mime_type: str) -> None:
        self._request("POST", f"/storage/v1/object/{bucket}/{key}", content=content, mime=mime_type)

    def download(self, bucket: str, key: str) -> bytes:
        return self._request("GET", f"/storage/v1/object/authenticated/{bucket}/{key}").content

    def delete(self, bucket: str, key: str) -> None:
        # A API de Storage remove objetos por uma lista de prefixes. Não tocar
        # diretamente nas tabelas internas do schema ``storage``.
        self._request("DELETE", f"/storage/v1/object/{bucket}", json_payload={"prefixes": [key]})


@dataclass(frozen=True)
class Asset:
    id: int
    original_name: str
    display_name: str
    mime_type: str
    byte_size: int
    category: str
    status: str
    storage_bucket: str
    storage_object_key: str
    sha256: str


def _asset(row) -> Asset:
    return Asset(**{key: row[key] for key in Asset.__dataclass_fields__})


def list_assets(conn: Database, actor: Actor, category: str | None = None, search: str = "", include_archived=False) -> list[Asset]:
    require(actor, Permission.VIEW_FILES)
    sql, params = "SELECT * FROM file_assets WHERE 1=1", []
    if not include_archived:
        sql += " AND status = 'ativo'"
    if category:
        sql += " AND category = ?"; params.append(category)
    rows = [_asset(r) for r in conn.execute(sql + " ORDER BY id DESC", tuple(params)).fetchall()]
    term = search.casefold().strip()
    return [a for a in rows if not term or term in a.display_name.casefold() or term in a.original_name.casefold()]


def upload_asset(conn: Database, storage: Storage, actor: Actor, original_name: str, content: bytes, mime: str | None, category: str = "operacional") -> Asset:
    require(actor, Permission.UPLOAD_FILES)
    if category not in {"operacional", "modelo"}:
        raise FileLibraryError("Categoria de arquivo inválida.")
    validated: ValidatedOperationalFile = validate_operational_file(original_name, content, mime)
    key = f"{category}/{uuid.uuid4().hex}.{validated.extension}"
    storage.upload(BUCKET, key, content, validated.mime_type)
    try:
        with transaction(conn):
            asset_id = _insert(conn, "INSERT INTO file_assets (original_name, display_name, file_extension, mime_type, byte_size, storage_bucket, storage_object_key, sha256, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (validated.original_name, validated.display_name, validated.extension, validated.mime_type, validated.byte_size, BUCKET, key, validated.sha256, category))
            log_event(conn, "arquivo_enviado", "file_assets", asset_id, f"Arquivo operacional enviado: {validated.display_name}")
            row = conn.execute("SELECT * FROM file_assets WHERE id = ?", (asset_id,)).fetchone()
            return _asset(row)
    except Exception:
        try: storage.delete(BUCKET, key)
        except Exception: pass  # reconciliação manual documentada; não mascarar o erro primário
        raise


def download_asset(conn: Database, storage: Storage, actor: Actor, asset_id: int) -> tuple[Asset, bytes]:
    require(actor, Permission.DOWNLOAD_FILES)
    row = conn.execute("SELECT * FROM file_assets WHERE id = ? AND status = 'ativo'", (asset_id,)).fetchone()
    if not row: raise FileLibraryError("Arquivo não encontrado ou arquivado.")
    asset = _asset(row)
    content = storage.download(asset.storage_bucket, asset.storage_object_key)
    import hashlib
    if hashlib.sha256(content).hexdigest() != asset.sha256:
        raise FileLibraryError("Falha de integridade do arquivo armazenado.")
    return asset, content


def archive_asset(conn: Database, actor: Actor, asset_id: int) -> None:
    require(actor, Permission.ARCHIVE_FILES)
    with transaction(conn):
        result = conn.execute("UPDATE file_assets SET status = 'arquivado' WHERE id = ? AND status = 'ativo'", (asset_id,))
        if result.rowcount != 1: raise FileLibraryError("Arquivo não encontrado ou já arquivado.")
        log_event(conn, "arquivo_arquivado", "file_assets", asset_id, "Arquivo arquivado")
