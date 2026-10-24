"""Autorização de servidor para o Agende Bem.

Os papéis ficam em ``agende_bem.app_users`` e nunca em user_metadata do JWT.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "administrador"
    RECEPTION = "recepcao"
    READ = "leitura"


class Permission(StrEnum):
    VIEW_AGENDA = "view_agenda"
    MANAGE_AGENDA = "manage_agenda"
    MANAGE_WAITING = "manage_waiting"
    CONFIRM_FIT_IN = "confirm_fit_in"
    VIEW_AUDIT = "view_audit"
    VIEW_FILES = "view_files"
    DOWNLOAD_FILES = "download_files"
    UPLOAD_FILES = "upload_files"
    ARCHIVE_FILES = "archive_files"
    MANAGE_TEMPLATES = "manage_templates"
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_USERS = "manage_users"


_MATRIX: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTION: frozenset({
        Permission.VIEW_AGENDA, Permission.MANAGE_AGENDA, Permission.MANAGE_WAITING,
        Permission.CONFIRM_FIT_IN, Permission.VIEW_AUDIT, Permission.VIEW_FILES,
        Permission.DOWNLOAD_FILES,
    }),
    Role.READ: frozenset({Permission.VIEW_AGENDA, Permission.VIEW_AUDIT, Permission.VIEW_FILES,
                          Permission.DOWNLOAD_FILES}),
}


class AccessDenied(PermissionError):
    """A sessão é válida, mas não pode executar a operação."""


@dataclass(frozen=True)
class Actor:
    user_id: str
    email: str
    role: Role


def allowed(actor: Actor | None, permission: Permission) -> bool:
    return actor is not None and permission in _MATRIX[actor.role]


def require(actor: Actor | None, permission: Permission) -> None:
    if not allowed(actor, permission):
        raise AccessDenied("Você não tem permissão para esta operação.")


def role_permissions(role: Role) -> frozenset[Permission]:
    return _MATRIX[role]
