"""Fixtures compartilhadas.

Os testes de serviço e CSV rodam no SQLite e, quando ``TEST_PG_ADMIN_URL`` está
definida, também no PostgreSQL. Exemplo (cluster local descartável):

    TEST_PG_ADMIN_URL=postgresql://postgres@127.0.0.1:55432/postgres python -m pytest

O banco de teste é criado do zero, as migrations são aplicadas com ``migrate.py``
e a aplicação conecta com o papel de privilégio mínimo ``agende_bem_app``.
"""
import os
import secrets
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
from database import connect  # noqa: E402
from seed import reset_demo  # noqa: E402

DEMO_DAY = date(2026, 10, 23)
PG_ADMIN_URL = os.environ.get("TEST_PG_ADMIN_URL")
PG_EXISTING = bool(os.environ.get("TEST_PG_EXISTING_APP_URL"))
PG_PROJECT_REF = os.environ.get("TEST_PG_PROJECT_REF")
SENTINEL = "public.agende_bem_teste_sentinela"
PG_TEST_DB = "agende_bem_test"
BACKENDS = ["sqlite", "postgres"]


def _with_db(url: str, dbname: str, **extra) -> str:
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(url)
    params.update(dbname=dbname, **extra)
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def pg_urls():
    """Cria o banco de teste, aplica migrations e devolve (admin_url, app_url).

    Modo "banco existente" (ex.: Supabase real já migrado): defina
    TEST_PG_EXISTING_ADMIN_URL, TEST_PG_EXISTING_APP_URL e TEST_PG_PROJECT_REF.
    Nada é criado além de uma tabela-sentinela temporária em public, removida ao final.
    """
    if PG_EXISTING:
        yield from _existing_pg_urls()
        return
    if not PG_ADMIN_URL:
        pytest.skip("TEST_PG_ADMIN_URL não definida: testes PostgreSQL ignorados.")
    import psycopg

    import migrate

    with psycopg.connect(PG_ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {PG_TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {PG_TEST_DB}")
        # Papéis da API do Supabase, para validar que ficam sem acesso.
        for role in ("anon", "authenticated"):
            exists = admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            if not exists:
                admin.execute(f"CREATE ROLE {role} NOLOGIN")

    admin_url = _with_db(PG_ADMIN_URL, PG_TEST_DB)
    expected_migrations = [path.stem for path in database.migration_files("postgres")]
    assert migrate.migrate(admin_url) == expected_migrations

    password = secrets.token_urlsafe(24)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            psycopg.sql.SQL("ALTER ROLE agende_bem_app WITH LOGIN PASSWORD {}").format(
                psycopg.sql.Literal(password)
            )
        )
        # Simula o "public" do Supabase com uma tabela que o reset nunca deve tocar.
        admin.execute(f"CREATE TABLE {SENTINEL} (id int)")
        admin.execute(f"INSERT INTO {SENTINEL} VALUES (1)")
    app_url = _with_db(PG_ADMIN_URL, PG_TEST_DB, user="agende_bem_app", password=password)
    yield admin_url, app_url
    database.close_pools()


def _existing_pg_urls():
    import psycopg

    admin_url = os.environ["TEST_PG_EXISTING_ADMIN_URL"]
    app_url = os.environ["TEST_PG_EXISTING_APP_URL"]
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"CREATE TABLE IF NOT EXISTS {SENTINEL} (id int)")
        admin.execute(f"REVOKE ALL ON {SENTINEL} FROM anon, authenticated")
        admin.execute(f"INSERT INTO {SENTINEL} VALUES (1)")
    try:
        yield admin_url, app_url
    finally:
        database.close_pools()
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(f"DROP TABLE IF EXISTS {SENTINEL}")


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def open_db(backend, db_file, request, monkeypatch):
    """Fábrica de conexões para o banco do teste (permite simular reinícios)."""
    if backend == "sqlite":
        monkeypatch.delenv("DATABASE_URL", raising=False)
        return lambda: connect(db_file)
    _, app_url = request.getfixturevalue("pg_urls")
    monkeypatch.setenv("DATABASE_URL", app_url)
    return lambda: connect()


@pytest.fixture
def conn(open_db):
    connection = open_db()
    reset_demo(connection, DEMO_DAY)
    yield connection
    connection.close()
