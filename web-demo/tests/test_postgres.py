"""Integração específica do PostgreSQL: concorrência, privilégios, migrations e TLS."""
import threading

import pytest

import database
import migrate
import services
from conftest import DEMO_DAY
from database import DatabaseError, IntegrityError, connect, secure_conninfo
from models import ValidationError
from seed import reset_demo

psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def pg(pg_urls, monkeypatch):
    admin_url, app_url = pg_urls
    monkeypatch.setenv("DATABASE_URL", app_url)
    db = connect()
    reset_demo(db, DEMO_DAY)
    return db


def admin(pg_urls):
    return psycopg.connect(pg_urls[0], autocommit=True)


def cancel_marcos(db):
    marcos = next(a for a in services.list_appointments(db) if a.patient_name == "Marcos Vieira")
    return services.cancel_appointment(db, marcos.id)


# --------------------------------------------------------------- concorrência

def test_double_booking_same_slot_only_one_wins(pg, pg_urls):
    """Duas recepcionistas confirmam candidatos diferentes no mesmo horário ao mesmo tempo."""
    window = cancel_marcos(pg)
    evals = services.evaluate_window(pg, window)
    paula, gabriel = evals[0], evals[1]
    barrier = threading.Barrier(2)
    outcomes = []

    def confirm(ev):
        db = connect()  # cada "sessão" com sua própria conexão do pool
        barrier.wait()
        try:
            services.confirm_fit_in(db, ev.entry.id, window.professional_id, ev.start)
            outcomes.append(("ok", ev.entry.patient_name))
        except ValidationError as exc:
            outcomes.append(("recusado", str(exc)))

    threads = [threading.Thread(target=confirm, args=(ev,)) for ev in (paula, gabriel)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(o[0] for o in outcomes) == ["ok", "recusado"]
    at_slot = [a for a in services.list_appointments(pg)
               if a.is_active and a.professional_id == window.professional_id and a.start == window.start]
    assert len(at_slot) == 1
    # Quem perdeu continua ativo na lista de espera (rollback completo).
    loser = next(o for o in outcomes if o[0] == "recusado")
    assert loser
    active = {e.patient_name for e in services.list_waiting(pg, "ativo")}
    assert len({"Paula Andrade", "Gabriel Moreira"} & active) == 1


def test_database_constraint_blocks_overlap_even_without_app_checks(pg):
    helena = services.list_professionals(pg)[0]
    with pytest.raises(IntegrityError):
        pg.execute(
            "INSERT INTO appointments (patient_name, professional_id, day, start_time, duration_min) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Teste Direto", helena.id, DEMO_DAY, "09:15", 30),
        )
    # Consultas canceladas não bloqueiam o horário.
    cancel_marcos(pg)
    pg.execute(
        "INSERT INTO appointments (patient_name, professional_id, day, start_time, duration_min) "
        "VALUES (?, ?, ?, ?, ?)",
        ("Teste Direto", helena.id, DEMO_DAY, "09:30", 30),
    )


def test_failed_transaction_rolls_back_everything(pg):
    before = len(services.list_appointments(pg))
    with pytest.raises(RuntimeError):
        with database.transaction(pg):
            services.log_event(pg, "teste", "system", None, "deve sumir")
            raise RuntimeError("falha simulada")
    assert len(services.list_appointments(pg)) == before
    assert all(e["event_type"] != "teste" for e in services.recent_events(pg, 50))


# ------------------------------------------------------- privilégios e API

def test_app_role_has_no_ddl_and_no_other_schemas(pg):
    for sql in (
        "CREATE TABLE agende_bem.invasora (id int)",
        "CREATE TABLE public.invasora (id int)",
        "SELECT * FROM public.sentinela",
        "DROP TABLE appointments",
        "TRUNCATE appointments",
    ):
        with pytest.raises(Exception) as exc:
            pg.execute(sql)
        assert isinstance(exc.value, (psycopg.errors.InsufficientPrivilege, DatabaseError)), sql


def test_supabase_api_roles_cannot_read_private_schema(pg_urls):
    with admin(pg_urls) as conn:
        for role in ("anon", "authenticated"):
            for table in ("appointments", "waiting_list", "audit_events"):
                allowed = conn.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT')", (role, f"agende_bem.{table}")
                ).fetchone()[0]
                assert allowed is False, (role, table)
            assert conn.execute(
                "SELECT has_schema_privilege(%s, 'agende_bem', 'USAGE')", (role,)
            ).fetchone()[0] is False
            assert conn.execute(
                "SELECT has_function_privilege(%s, 'agende_bem.reset_demo_data()', 'EXECUTE')", (role,)
            ).fetchone()[0] is False
        rls = conn.execute(
            "SELECT bool_and(relrowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'agende_bem' AND c.relkind = 'r' AND c.relname <> 'schema_migrations'"
        ).fetchone()[0]
        assert rls is True


def test_reset_only_touches_private_schema(pg, pg_urls):
    cancel_marcos(pg)
    reset_demo(pg, DEMO_DAY)
    assert services.dashboard_stats(pg).cancelled == 0
    assert min(a.id for a in services.list_appointments(pg)) == 1  # identidade reiniciada
    with admin(pg_urls) as conn:
        assert conn.execute("SELECT count(*) FROM public.sentinela").fetchone()[0] == 1


def test_seed_is_idempotent_under_concurrent_startup(pg):
    pg.execute("SELECT agende_bem.reset_demo_data()")
    from seed import ensure_seeded

    results = []
    threads = [threading.Thread(target=lambda: results.append(ensure_seeded(connect()))) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(results) == [False, False, True]
    assert len(services.list_professionals(pg)) == 3


def test_app_refuses_unmigrated_database(pg_urls, monkeypatch):
    with admin(pg_urls) as conn:
        conn.execute("DROP DATABASE IF EXISTS agende_bem_vazio WITH (FORCE)")
        conn.execute("CREATE DATABASE agende_bem_vazio")
    url = pg_urls[1].replace("dbname=agende_bem_test", "dbname=agende_bem_vazio")
    with pytest.raises(DatabaseError, match="migrate"):
        database.init_db(database.PostgresDatabase(url))


# ------------------------------------------------------- migrations e TLS

def test_migrations_are_idempotent(pg_urls):
    assert migrate.migrate(pg_urls[0]) == []


def test_migrate_refuses_remote_target_without_matching_project_ref():
    remote = "postgresql://postgres:x@db.abcdefghijklmnop.supabase.co:5432/postgres"
    with pytest.raises(DatabaseError, match="project-ref"):
        migrate.check_target(secure_conninfo(remote), None)
    with pytest.raises(DatabaseError, match="não pertence"):
        migrate.check_target(secure_conninfo(remote), "outroprojeto123")
    migrate.check_target(secure_conninfo(remote), "abcdefghijklmnop")


def test_remote_connections_require_tls():
    from psycopg.conninfo import conninfo_to_dict

    remote = "postgresql://u:p@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
    assert conninfo_to_dict(secure_conninfo(remote))["sslmode"] == "require"
    with pytest.raises(DatabaseError, match="sslmode"):
        secure_conninfo(remote + "?sslmode=disable")
    assert conninfo_to_dict(secure_conninfo(remote + "?sslmode=verify-full"))["sslmode"] == "verify-full"


def test_pool_recovers_after_server_side_disconnect(pg, pg_urls):
    """Simula o pooler derrubando conexões ociosas: o pool descarta e reconecta."""
    services.list_appointments(pg)
    with admin(pg_urls) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE usename = 'agende_bem_app' AND pid <> pg_backend_pid()"
        )
    assert len(services.list_appointments(connect())) == 19
