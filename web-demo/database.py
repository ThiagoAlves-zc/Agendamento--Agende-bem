"""Acesso ao banco: SQLite (local) ou PostgreSQL/Supabase (``DATABASE_URL``).

Os serviços usam uma interface única:

- ``db.execute(sql, params)`` com placeholders ``?`` e resultado já materializado;
- ``with transaction(db):`` para escritas atômicas com bloqueio de escrita
  (``BEGIN IMMEDIATE`` no SQLite, advisory lock transacional no PostgreSQL).

No PostgreSQL as conexões vêm de um pool pequeno por processo, a conexão é
sempre criptografada (``sslmode`` >= ``require``) e o esquema é criado apenas
pelas migrations (``migrate.py``), nunca pela aplicação.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "agende_bem.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"
PG_SCHEMA = "agende_bem"
# Chave fixa do advisory lock: serializa as escritas da aplicação, como o BEGIN IMMEDIATE.
PG_WRITE_LOCK = 734_202_610
_SECURE_SSLMODES = {"require", "verify-ca", "verify-full"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class DatabaseError(RuntimeError):
    """Falha de configuração ou de esquema do banco."""


class IntegrityError(DatabaseError):
    """Violação de restrição do banco (ex.: sobreposição de consultas)."""


class Result:
    """Resultado materializado: a conexão pode voltar ao pool imediatamente."""

    def __init__(self, rows: list, rowcount: int):
        self._rows = rows
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


# ------------------------------------------------------------------- SQLite

class SqliteDatabase:
    dialect = "sqlite"
    now_sql = "datetime('now', 'localtime')"

    def __init__(self, path: str | Path):
        target = Path(path)
        if str(target) != ":memory:":
            target.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(target), isolation_level=None, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _adapt(params: Sequence[Any]) -> tuple:
        return tuple(p.isoformat() if isinstance(p, (date, datetime)) else p for p in params)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Result:
        try:
            cur = self._conn.execute(sql, self._adapt(params))
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(str(exc)) from exc
        rows = cur.fetchall() if cur.description else []
        return Result(rows, cur.rowcount)

    def executescript(self, script: str) -> None:
        self._conn.executescript(script)

    @contextmanager
    def transaction(self) -> Iterator["SqliteDatabase"]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def close(self) -> None:
        self._conn.close()


# --------------------------------------------------------------- PostgreSQL

_pools: dict[str, Any] = {}
_pools_lock = threading.Lock()


def secure_conninfo(url: str) -> str:
    """Exige conexão criptografada fora de localhost e nunca registra a senha."""
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    try:
        params = conninfo_to_dict(url)
    except Exception as exc:  # mensagem do driver pode conter a URL
        raise DatabaseError("DATABASE_URL inválida.") from exc
    host = str(params.get("host", ""))
    sslmode = params.get("sslmode")
    if host not in _LOCAL_HOSTS:
        if sslmode is None:
            params["sslmode"] = "require"
        elif sslmode not in _SECURE_SSLMODES:
            raise DatabaseError("Conexões remotas exigem sslmode=require ou superior.")
    params.setdefault("application_name", "agende-bem")
    params.setdefault("connect_timeout", "10")
    return make_conninfo(**params)


def _get_pool(url: str):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    with _pools_lock:
        pool = _pools.get(url)
        if pool is None:
            pool = ConnectionPool(
                secure_conninfo(url),
                min_size=0,
                max_size=int(os.environ.get("DB_POOL_MAX_SIZE", "3")),
                max_idle=60,
                timeout=15,
                check=ConnectionPool.check_connection,  # descarta conexões derrubadas pelo pooler
                kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
                name="agende-bem",
                open=True,
            )
            _pools[url] = pool
        return pool


def close_pools() -> None:
    with _pools_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


class PostgresDatabase:
    """Fachada leve sobre um pool compartilhado; uma instância por execução da página."""

    dialect = "postgres"
    now_sql = "now()"

    def __init__(self, url: str):
        self._pool = _get_pool(url)
        self._tx_conn = None

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s")

    def _run(self, conn, sql: str, params: Sequence[Any]) -> Result:
        import psycopg

        try:
            cur = conn.execute(self._sql(sql), tuple(params))
        except psycopg.errors.IntegrityError as exc:
            raise IntegrityError(exc.diag.constraint_name or exc.sqlstate or "integridade") from exc
        rows = cur.fetchall() if cur.description else []
        return Result(rows, cur.rowcount)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Result:
        if self._tx_conn is not None:
            return self._run(self._tx_conn, sql, params)
        with self._pool.connection() as conn:
            return self._run(conn, sql, params)

    @contextmanager
    def transaction(self) -> Iterator["PostgresDatabase"]:
        if self._tx_conn is not None:
            raise DatabaseError("Transações aninhadas não são suportadas.")
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (PG_WRITE_LOCK,))
                self._tx_conn = conn
                try:
                    yield self
                finally:
                    self._tx_conn = None

    def close(self) -> None:
        """O pool é compartilhado pelo processo; nada a liberar por instância."""


Database = SqliteDatabase | PostgresDatabase


# -------------------------------------------------------------------- API

def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def db_path() -> Path:
    """Caminho do SQLite local; pode ser sobrescrito por AGENDE_BEM_DB."""
    return Path(os.environ.get("AGENDE_BEM_DB", DEFAULT_DB_PATH))


def connect(path: str | Path | None = None) -> Database:
    """SQLite se ``path`` for informado ou não houver DATABASE_URL; senão PostgreSQL."""
    if path is None and database_url():
        return PostgresDatabase(database_url())
    if path is None and os.environ.get("AGENDE_BEM_REQUIRE_DATABASE_URL") == "true":
        # Em container o disco é efêmero: sem DATABASE_URL os dados se perderiam.
        raise DatabaseError("DATABASE_URL não configurada neste ambiente.")
    return SqliteDatabase(path if path is not None else db_path())


@contextmanager
def transaction(db: Database) -> Iterator[Database]:
    with db.transaction() as tx:
        yield tx


def migration_files(dialect: str) -> list[Path]:
    return sorted((MIGRATIONS_DIR / dialect).glob("[0-9][0-9][0-9][0-9]_*.sql"))


def init_db(db: Database) -> None:
    """SQLite: aplica as migrations pendentes. PostgreSQL: apenas verifica o esquema.

    Em produção o usuário da aplicação não tem permissão de DDL; as migrations
    do PostgreSQL são aplicadas pelo operador com ``python migrate.py``.
    """
    if db.dialect == "sqlite":
        db.executescript(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {r["version"] for r in db.execute("SELECT version FROM schema_migrations")}
        for path in migration_files("sqlite"):
            if path.stem not in applied:
                db.executescript(path.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (path.stem,))
        return

    expected = migration_files("postgres")[-1].stem
    try:
        row = db.execute(
            "SELECT max(version) AS v FROM agende_bem.schema_migrations"
        ).fetchone()
    except Exception as exc:
        raise DatabaseError(
            "Esquema 'agende_bem' indisponível. Aplique as migrations com migrate.py."
        ) from exc
    if not row or row["v"] is None or row["v"] < expected:
        raise DatabaseError(f"Migrations pendentes no PostgreSQL (esperado: {expected}).")
    schema = db.execute("SELECT current_schema() AS s").fetchone()["s"]
    if schema != PG_SCHEMA:
        raise DatabaseError(
            f"search_path do usuário deve apontar para '{PG_SCHEMA}' (atual: {schema})."
        )
