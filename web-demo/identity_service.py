"""Resolução de identidade e administração de papéis no limite do servidor.

O JWT confirma quem autenticou; o papel é lido exclusivamente de
``app_users``. Portanto, um valor enviado pelo cliente nunca escolhe um papel.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from authorization import AccessDenied, Actor, Permission, Role, require
from database import Database, transaction
from services import log_event


class IdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppUser:
    user_id: str
    email: str
    role: Role
    active: bool


def _as_user(row) -> AppUser:
    return AppUser(str(row["user_id"]), str(row["email"]), Role(row["role"]), bool(row["active"]))


def actor_for_verified_user(conn: Database, user_id: str, email: str) -> Actor:
    """Resolve a identidade retornada pela API Auth, sem aceitar role do cliente."""
    row = conn.execute(
        "SELECT user_id, email, role, active FROM app_users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row or not bool(row["active"]) or str(row["email"]).casefold() != email.casefold():
        raise AccessDenied("Sua conta não possui acesso operacional ativo.")
    user = _as_user(row)
    return Actor(user.user_id, user.email, user.role)


def list_users(conn: Database, actor: Actor) -> list[AppUser]:
    require(actor, Permission.MANAGE_USERS)
    return [_as_user(row) for row in conn.execute(
        "SELECT user_id, email, role, active FROM app_users ORDER BY lower(email)"
    ).fetchall()]


def set_user_role(conn: Database, actor: Actor, user_id: str, role: Role, active: bool | None = None) -> None:
    require(actor, Permission.MANAGE_USERS)
    if actor.user_id == user_id and (role != Role.ADMIN or active is False):
        raise IdentityError("Um administrador não pode remover o próprio acesso por esta tela.")
    with transaction(conn):
        if active is None:
            result = conn.execute("UPDATE app_users SET role = ? WHERE user_id = ?", (role.value, user_id))
        else:
            result = conn.execute("UPDATE app_users SET role = ?, active = ? WHERE user_id = ?", (role.value, active, user_id))
        if result.rowcount != 1:
            raise IdentityError("Usuário operacional não encontrado.")
        log_event(conn, "permissao_atualizada", "app_users", None, "Permissões de usuário atualizadas")


def bootstrap_first_admin(conn: Database, *, verified_user_id: str, verified_email: str, bootstrap_token: str) -> Actor:
    """Procedimento único, invocável só por operador no servidor.

    Requer um token de uso único configurado fora do código e uma identidade que
    já tenha sido verificada pelo Supabase Auth. Não existe rota ou formulário
    público para este bootstrap.
    """
    expected = os.environ.get("AGENDE_BEM_BOOTSTRAP_TOKEN", "")
    if not expected or not hmac.compare_digest(bootstrap_token, expected):
        raise AccessDenied("Bootstrap não autorizado.")
    if not verified_user_id or "@" not in verified_email:
        raise IdentityError("Identidade verificada inválida.")
    with transaction(conn):
        existing = conn.execute("SELECT user_id FROM app_users LIMIT 1").fetchone()
        if existing:
            raise IdentityError("O primeiro administrador já foi definido.")
        conn.execute(
            "INSERT INTO app_users (user_id, email, role, active) VALUES (?, ?, ?, ?)",
            (verified_user_id, verified_email.strip(), Role.ADMIN.value, True),
        )
        log_event(conn, "primeiro_administrador", "app_users", None, "Primeiro administrador definido")
    return Actor(verified_user_id, verified_email.strip(), Role.ADMIN)
