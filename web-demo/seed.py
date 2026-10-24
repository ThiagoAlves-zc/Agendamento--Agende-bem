"""Dados sintéticos de demonstração (nenhum dado real de paciente).

Uso: ``python seed.py`` restaura o cenário de demonstração no banco configurado.

Cenário: a consulta de 30 min de Marcos Vieira com a Dra. Helena Prado às
09:30 é a candidata a cancelamento. Na lista de espera há candidatos
compatíveis (Paula, Gabriel, Juliana) e incompatíveis por profissional,
duração, disponibilidade e conflito de horário.
"""
from __future__ import annotations

from datetime import date, timedelta

from database import Database, connect, init_db, transaction
from models import today_local
from services import _insert, log_event, set_agenda_day

PROFESSIONALS = [
    # nome, especialidade, início, fim do expediente
    ("Dra. Helena Prado", "Clínica Geral", "08:00", "12:00"),
    ("Dr. Rafael Mendes", "Cardiologia", "08:00", "12:00"),
    ("Dra. Lívia Tanaka", "Dermatologia", "08:00", "12:00"),
]

# índice do profissional, horário, duração (min), paciente
APPOINTMENTS = [
    (0, "08:00", 30, "Ana Beatriz Souza"),
    (0, "08:30", 30, "Carlos Eduardo Lima"),
    (0, "09:00", 30, "Fernanda Rocha"),
    (0, "09:30", 30, "Marcos Vieira"),  # cancelamento demonstrável
    (0, "10:00", 45, "Patrícia Gomes"),
    (0, "10:45", 20, "João Pedro Alves"),
    (0, "11:05", 30, "Luana Martins"),
    (1, "08:00", 45, "Roberto Nunes"),
    (1, "08:45", 45, "Sílvia Castro"),
    (1, "09:30", 30, "Thiago Barros"),
    (1, "10:00", 20, "Vanessa Ribeiro"),
    (1, "10:20", 45, "Eduardo Farias"),
    (2, "08:00", 20, "Bruna Teixeira"),
    (2, "08:20", 20, "Gustavo Reis"),
    (2, "08:40", 30, "Isabela Duarte"),
    (2, "09:40", 45, "Leonardo Pires"),
    (2, "10:25", 20, "Mariana Costa"),
    (2, "10:45", 30, "Otávio Santana"),
    (2, "11:15", 45, "Renata Alencar"),
]

# paciente, profissionais aceitos (índices), duração, disponível de/até, dias de espera, observação
WAITING = [
    ("Paula Andrade", (0, 1), 30, "09:00", "12:00", 12, "Prefere manhã"),
    ("Gabriel Moreira", (0,), 20, "09:00", "11:00", 12, ""),
    ("Juliana Freitas", (0,), 30, "08:00", "11:00", 5, ""),
    ("Ricardo Sampaio", (0,), 45, "08:00", "12:00", 20, "Retorno"),
    ("Camila Ferraz", (2,), 30, "08:00", "12:00", 15, ""),
    ("Diego Carvalho", (0,), 30, "10:30", "12:00", 9, "Só após 10h30"),
    ("Thiago Barros", (0,), 30, "08:00", "12:00", 30, "Já tem consulta com Dr. Rafael"),
]


TABLES = ("audit_events", "appointments", "waiting_list", "professionals", "settings")


def _clear(conn: Database) -> None:
    """Esvazia somente as tabelas do Agende Bem (nomes fixos, sem entrada do usuário)."""
    if conn.dialect == "postgres":
        # Função SECURITY DEFINER da migration 0003: o papel da aplicação não tem TRUNCATE.
        conn.execute("SELECT agende_bem.reset_demo_data()")
        return
    for table in TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence")


def _is_empty(conn: Database) -> bool:
    return conn.execute("SELECT COUNT(*) AS n FROM professionals").fetchone()["n"] == 0


def reset_demo(conn: Database, day: date | None = None, only_if_empty: bool = False) -> bool:
    """Recria o cenário de demonstração em uma transação. Retorna se houve carga.

    ``only_if_empty`` verifica o banco já dentro da transação (com o bloqueio de
    escrita), evitando carga duplicada quando duas instâncias iniciam juntas.
    """
    day = day or today_local()
    init_db(conn)
    with transaction(conn):
        if only_if_empty and not _is_empty(conn):
            return False
        _clear(conn)

        ids = []
        for name, specialty, start, end in PROFESSIONALS:
            ids.append(_insert(
                conn,
                "INSERT INTO professionals (name, specialty, day_start, day_end) VALUES (?, ?, ?, ?)",
                (name, specialty, start, end),
            ))

        for prof, start, duration, patient in APPOINTMENTS:
            conn.execute(
                "INSERT INTO appointments (patient_name, professional_id, day, start_time, duration_min) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient, ids[prof], day, start, duration),
            )

        for patient, profs, duration, start, end, days, notes in WAITING:
            conn.execute(
                "INSERT INTO waiting_list (patient_name, professional_ids, duration_min, "
                "available_from, available_until, requested_on, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    patient,
                    ",".join(str(ids[p]) for p in profs),
                    duration,
                    start,
                    end,
                    day - timedelta(days=days),
                    notes,
                ),
            )

        set_agenda_day(conn, day)
        log_event(conn, "dados_demo_restaurados", "system", None, "Cenário de demonstração carregado")
    return True


def ensure_seeded(conn: Database) -> bool:
    """Carrega a demonstração somente se o banco estiver vazio."""
    init_db(conn)
    if not _is_empty(conn):
        return False
    return reset_demo(conn, only_if_empty=True)


if __name__ == "__main__":
    connection = connect()
    reset_demo(connection)
    print("Dados de demonstração restaurados.")
