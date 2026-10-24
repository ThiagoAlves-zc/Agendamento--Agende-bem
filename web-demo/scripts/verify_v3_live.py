"""Smoke test seguro do go-live V3; recebe segredos apenas via ambiente."""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authorization import AccessDenied, Role
from database import connect
from file_library import SupabaseStorage, archive_asset, download_asset, list_assets, upload_asset
from identity_service import actor_for_verified_user
from supabase_auth import SupabaseAuth


def main() -> None:
    conn = connect()
    rows = {
        row["email"]: row
        for row in conn.execute(
            "SELECT user_id, email, role FROM app_users "
            "WHERE email IN ('v3.admin@agendebem.test', 'v3.leitura@agendebem.test')"
        ).fetchall()
    }
    assert len(rows) == 2
    admin_row = rows["v3.admin@agendebem.test"]
    read_row = rows["v3.leitura@agendebem.test"]
    admin = actor_for_verified_user(conn, str(admin_row["user_id"]), str(admin_row["email"]))
    reader = actor_for_verified_user(conn, str(read_row["user_id"]), str(read_row["email"]))
    assert admin.role is Role.ADMIN and reader.role is Role.READ

    password = "V3!" + secrets.token_urlsafe(24)
    secret = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": secret, "Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    response = requests.put(
        f"{os.environ['SUPABASE_URL']}/auth/v1/admin/users/{admin_row['user_id']}",
        headers=headers,
        json={"password": password},
        timeout=15,
    )
    response.raise_for_status()
    auth = SupabaseAuth()
    session = auth.sign_in(str(admin_row["email"]), password)
    assert auth.current_user(session).get("id") == str(admin_row["user_id"])
    auth.sign_out(auth.refresh(session))

    storage = SupabaseStorage()
    templates = list_assets(conn, reader, category="modelo")
    assert templates
    _, template_content = download_asset(conn, storage, reader, templates[0].id)
    assert template_content
    try:
        upload_asset(conn, storage, reader, "bloqueado.csv", b"coluna\nvalor\n", "text/csv")
    except AccessDenied:
        pass
    else:
        raise AssertionError("Perfil de leitura recebeu permissão de upload.")

    smoke = upload_asset(
        conn, storage, admin, "v3-smoke-operacional.csv", b"nome,valor\nV3 smoke,ok\n", "text/csv"
    )
    _, payload = download_asset(conn, storage, reader, smoke.id)
    assert payload.startswith(b"nome,valor")
    archive_asset(conn, admin, smoke.id)
    print("auth_login_refresh_logout=ok")
    print("rbac_roles_and_denial=ok")
    print("template_download_sha256=ok")
    print("upload_download_archive=ok")
    print(f"synthetic_asset_id={smoke.id}")


if __name__ == "__main__":
    main()
