"""Aplica as migrations PostgreSQL do Agende Bem.

Uso (credencial administrativa apenas na sessão do operador, nunca no Git):

    DATABASE_ADMIN_URL="postgresql://..." python migrate.py --project-ref <ref-do-projeto>
    python migrate.py --project-ref <ref> --dry-run      # só lista o que seria aplicado

Proteções:
- ``--project-ref`` precisa aparecer no host ou no usuário da URL, evitando aplicar
  o esquema por engano em outro projeto Supabase (ex.: CRM, TrilhaX);
- conexões remotas exigem TLS (``sslmode=require`` ou superior);
- cada migration roda em sua própria transação e é registrada em ``schema_migrations``.
"""
from __future__ import annotations

import argparse
import os
import sys

from database import PG_SCHEMA, DatabaseError, migration_files, secure_conninfo

_LOCAL = {"localhost", "127.0.0.1", "::1"}


def check_target(conninfo: str, project_ref: str | None) -> None:
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(conninfo)
    host, user = str(params.get("host", "")), str(params.get("user", ""))
    if host in _LOCAL:
        return
    if not project_ref:
        raise DatabaseError("Informe --project-ref para aplicar migrations em banco remoto.")
    if project_ref not in host and project_ref not in user:
        raise DatabaseError("A URL não pertence ao projeto informado em --project-ref. Abortado.")


def pending(conn) -> list:
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {PG_SCHEMA}.schema_migrations ("
        "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    applied = {r[0] for r in conn.execute(f"SELECT version FROM {PG_SCHEMA}.schema_migrations")}
    return [p for p in migration_files("postgres") if p.stem not in applied]


def migrate(url: str, project_ref: str | None = None, dry_run: bool = False) -> list[str]:
    import psycopg

    conninfo = secure_conninfo(url)
    check_target(conninfo, project_ref)
    done = []
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.transaction():
            todo = pending(conn)
        for path in todo:
            if dry_run:
                done.append(path.stem)
                continue
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    f"INSERT INTO {PG_SCHEMA}.schema_migrations (version) VALUES (%s)", (path.stem,)
                )
            done.append(path.stem)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-ref", help="ref do projeto Supabase de destino")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_ADMIN_URL")
    if not url:
        print("Defina DATABASE_ADMIN_URL na sessão (não grave em arquivo).", file=sys.stderr)
        return 2
    try:
        applied = migrate(url, args.project_ref, args.dry_run)
    except DatabaseError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    label = "Seriam aplicadas" if args.dry_run else "Aplicadas"
    print(f"{label}: {', '.join(applied) if applied else 'nenhuma (esquema atualizado)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
