import os

import pytest

from authorization import AccessDenied, Actor, Role
from identity_service import (
    IdentityError, actor_for_verified_user, bootstrap_first_admin, list_users, set_user_role,
)


def test_verified_identity_never_accepts_client_role_or_mismatched_email(conn):
    conn.execute("DELETE FROM app_users")
    user_id = "00000000-0000-0000-0000-000000000101"
    conn.execute("INSERT INTO app_users (user_id, email, role, active) VALUES (?, ?, ?, ?)", (user_id, "person@example.test", "leitura", True))
    actor = actor_for_verified_user(conn, user_id, "person@example.test")
    assert actor.role is Role.READ
    with pytest.raises(AccessDenied):
        actor_for_verified_user(conn, user_id, "other@example.test")
    with pytest.raises(AccessDenied):
        actor_for_verified_user(conn, "00000000-0000-0000-0000-000000000199", "person@example.test")


def test_only_admin_manages_users_and_cannot_lock_self_out(conn):
    conn.execute("DELETE FROM app_users")
    admin = Actor("00000000-0000-0000-0000-000000000102", "admin@example.test", Role.ADMIN)
    reader = Actor("00000000-0000-0000-0000-000000000103", "reader@example.test", Role.READ)
    conn.execute("INSERT INTO app_users (user_id, email, role, active) VALUES (?, ?, ?, ?)", (admin.user_id, admin.email, admin.role.value, True))
    conn.execute("INSERT INTO app_users (user_id, email, role, active) VALUES (?, ?, ?, ?)", (reader.user_id, reader.email, reader.role.value, True))
    with pytest.raises(AccessDenied):
        list_users(conn, reader)
    set_user_role(conn, admin, reader.user_id, Role.RECEPTION)
    assert actor_for_verified_user(conn, reader.user_id, reader.email).role is Role.RECEPTION
    with pytest.raises(IdentityError):
        set_user_role(conn, admin, admin.user_id, Role.READ)


def test_first_admin_bootstrap_is_once_only_and_server_secret_gated(conn, monkeypatch):
    conn.execute("DELETE FROM app_users")
    monkeypatch.setenv("AGENDE_BEM_BOOTSTRAP_TOKEN", "one-time-secret")
    with pytest.raises(AccessDenied):
        bootstrap_first_admin(conn, verified_user_id="00000000-0000-0000-0000-000000000104", verified_email="first@example.test", bootstrap_token="wrong")
    actor = bootstrap_first_admin(conn, verified_user_id="00000000-0000-0000-0000-000000000104", verified_email="first@example.test", bootstrap_token="one-time-secret")
    assert actor.role is Role.ADMIN
    with pytest.raises(IdentityError):
        bootstrap_first_admin(conn, verified_user_id="00000000-0000-0000-0000-000000000105", verified_email="second@example.test", bootstrap_token="one-time-secret")
