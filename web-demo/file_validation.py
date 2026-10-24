"""Validação determinística de arquivos operacionais antes do Storage.

O módulo não abre conexões nem envia conteúdo. A camada que integrar o Supabase
Storage deve chamá-lo antes de gerar a chave do objeto e registrar metadados.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePath

from models import ValidationError

MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_BY_EXTENSION = {
    "csv": "text/csv",
    "pdf": "application/pdf",
}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ValidatedOperationalFile:
    original_name: str
    display_name: str
    extension: str
    mime_type: str
    byte_size: int
    sha256: str


def _normal_name(value: str, label: str) -> str:
    name = unicodedata.normalize("NFC", str(value or "")).strip()
    if not name or len(name) > 255:
        raise ValidationError(f"{label} deve ter entre 1 e 255 caracteres.")
    if _CONTROL_CHARS.search(name) or "/" in name or "\\" in name or ".." in name:
        raise ValidationError(f"{label} contém caracteres ou caminho inválidos.")
    return name


def validate_operational_file(
    original_name: str, content: bytes, declared_mime: str | None = None
) -> ValidatedOperationalFile:
    """Valida CSV/PDF pequeno por extensão, MIME declarado e assinatura simples."""
    name = _normal_name(original_name, "Nome do arquivo")
    if PurePath(name).name != name:
        raise ValidationError("Nome do arquivo não pode incluir diretórios.")
    if not isinstance(content, bytes) or not content:
        raise ValidationError("O arquivo está vazio ou inválido.")
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError(f"O arquivo excede o limite de {MAX_FILE_BYTES // (1024 * 1024)} MB.")

    suffix = PurePath(name).suffix.lower().lstrip(".")
    expected_mime = ALLOWED_MIME_BY_EXTENSION.get(suffix)
    if expected_mime is None:
        raise ValidationError("Formato não permitido. Envie CSV ou PDF.")
    if declared_mime and declared_mime.lower().split(";", 1)[0].strip() != expected_mime:
        raise ValidationError("O tipo MIME informado não corresponde à extensão do arquivo.")
    if suffix == "pdf" and not content.startswith(b"%PDF-"):
        raise ValidationError("O conteúdo não possui assinatura PDF válida.")
    if suffix == "csv":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("CSV deve usar codificação UTF-8.") from exc

    stem = PurePath(name).stem.strip()
    return ValidatedOperationalFile(
        original_name=name,
        display_name=stem[:120] or name,
        extension=suffix,
        mime_type=expected_mime,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
