"""Operações da agenda sobre o SQLite (consultas parametrizadas, sem SQL concatenado)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import scheduler
from database import transaction
from models import (
    Appointment,
    Evaluation,
    MAX_PROFESSIONALS,
    ORIGIN_AGENDA,
    ORIGIN_FIT_IN,
    Professional,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    ValidationError,
    WAIT_ACTIVE,
    WAIT_REMOVED,
    WAIT_SCHEDULED,
    WaitingEntry,
    Window,
    fmt_time,
    parse_date,
    parse_time,
    validate_duration,
    validate_interval,
    validate_name,
)

MAX_NOTES = 200


# ------------------------------------------------------------------ helpers

def _professional(row: sqlite3.Row) -> Professional:
    return Professional(
        id=row["id"],
        name=row["name"],
        specialty=row["specialty"],
        day_start=parse_time(row["day_start"]),
        day_end=parse_time(row["day_end"]),
    )


def _appointment(row: sqlite3.Row) -> Appointment:
    return Appointment(
        id=row["id"],
        patient_name=row["patient_name"],
        professional_id=row["professional_id"],
        day=parse_date(row["day"]),
        start=parse_time(row["start_time"]),
        duration=row["duration_min"],
        status=row["status"],
        origin=row["origin"],
    )


def _waiting(row: sqlite3.Row) -> WaitingEntry:
    ids = tuple(int(x) for x in row["professional_ids"].split(",") if x)
    return WaitingEntry(
        id=row["id"],
        patient_name=row["patient_name"],
        professional_ids=ids,
        duration=row["duration_min"],
        available_from=parse_time(row["available_from"]),
        available_until=parse_time(row["available_until"]),
        requested_on=parse_date(row["requested_on"]),
        status=row["status"],
        notes=row["notes"],
    )


def log_event(
    conn: sqlite3.Connection, event_type: str, entity: str, entity_id: int | None, details: str
) -> None:
    conn.execute(
        "INSERT INTO audit_events (event_type, entity, entity_id, details) VALUES (?, ?, ?, ?)",
        (event_type, entity, entity_id, details),
    )


def recent_events(conn: sqlite3.Connection, limit: int = 8) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT created_at, event_type, details FROM audit_events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def find_overlaps(appointments: Iterable[Appointment]) -> list[str]:
    """Mensagens para consultas ativas sobrepostas (mesmo profissional ou mesmo paciente)."""
    active = sorted((a for a in appointments if a.is_active), key=lambda a: (a.day, a.start))
    problems = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if b.day != a.day or b.start >= a.end:
                continue
            if a.professional_id == b.professional_id:
                who = "mesmo profissional"
            elif a.patient_name.casefold() == b.patient_name.casefold():
                who = f"paciente {a.patient_name}"
            else:
                continue
            problems.append(
                f"Sobreposição ({who}): {a.patient_name} {fmt_time(a.start)}–{fmt_time(a.end)} "
                f"e {b.patient_name} {fmt_time(b.start)}–{fmt_time(b.end)}."
            )
    return problems


# ----------------------------------------------------------- configuração

def get_agenda_day(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT value FROM settings WHERE key = 'agenda_day'").fetchone()
    return parse_date(row["value"]) if row else date.today()


def set_agenda_day(conn: sqlite3.Connection, day: date) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('agenda_day', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (day.isoformat(),),
    )


# ------------------------------------------------------------ profissionais

def list_professionals(conn: sqlite3.Connection) -> list[Professional]:
    rows = conn.execute("SELECT * FROM professionals WHERE active = 1 ORDER BY id").fetchall()
    return [_professional(r) for r in rows]


def professional_names(conn: sqlite3.Connection) -> dict[int, str]:
    return {p.id: p.name for p in list_professionals(conn)}


def add_professional(
    conn: sqlite3.Connection, name: str, specialty: str, day_start: str, day_end: str
) -> int:
    name = validate_name(name, "Nome do profissional")
    start, end = parse_time(day_start), parse_time(day_end)
    validate_interval(start, end, "Expediente")
    with transaction(conn):
        count = conn.execute("SELECT COUNT(*) FROM professionals WHERE active = 1").fetchone()[0]
        if count >= MAX_PROFESSIONALS:
            raise ValidationError(f"Limite de {MAX_PROFESSIONALS} profissionais atingido.")
        cur = conn.execute(
            "INSERT INTO professionals (name, specialty, day_start, day_end) VALUES (?, ?, ?, ?)",
            (name, specialty.strip()[:60], fmt_time(start), fmt_time(end)),
        )
        log_event(conn, "profissional_cadastrado", "professionals", cur.lastrowid, name)
    return cur.lastrowid


# ------------------------------------------------------------- agendamentos

def list_appointments(conn: sqlite3.Connection, day: date | None = None) -> list[Appointment]:
    day = day or get_agenda_day(conn)
    rows = conn.execute(
        "SELECT * FROM appointments WHERE day = ? ORDER BY start_time, professional_id, id",
        (day.isoformat(),),
    ).fetchall()
    return [_appointment(r) for r in rows]


def create_appointment(
    conn: sqlite3.Connection,
    patient_name: str,
    professional_id: int,
    start: str,
    duration: int,
) -> int:
    """Cria consulta confirmada no dia da agenda, validando expediente e conflitos."""
    patient_name = validate_name(patient_name, "Nome do paciente")
    start_min = parse_time(start)
    duration = validate_duration(duration)
    with transaction(conn):
        day = get_agenda_day(conn)
        prof = _get_professional(conn, professional_id)
        if start_min < prof.day_start or start_min + duration > prof.day_end:
            raise ValidationError(
                f"Fora do expediente de {prof.name} "
                f"({fmt_time(prof.day_start)}–{fmt_time(prof.day_end)})."
            )
        candidate = Appointment(0, patient_name, professional_id, day, start_min, duration)
        problems = find_overlaps(list_appointments(conn, day) + [candidate])
        if problems:
            raise ValidationError(problems[0])
        cur = conn.execute(
            "INSERT INTO appointments (patient_name, professional_id, day, start_time, duration_min) "
            "VALUES (?, ?, ?, ?, ?)",
            (patient_name, professional_id, day.isoformat(), fmt_time(start_min), duration),
        )
        log_event(conn, "consulta_criada", "appointments", cur.lastrowid, patient_name)
    return cur.lastrowid


def cancel_appointment(conn: sqlite3.Connection, appointment_id: int) -> Window | None:
    """Marca a consulta como cancelada (preserva o registro) e retorna a janela liberada."""
    with transaction(conn):
        row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        if row is None:
            raise ValidationError("Consulta não encontrada.")
        appt = _appointment(row)
        if appt.status != STATUS_CONFIRMED:
            raise ValidationError("Esta consulta já está cancelada.")
        conn.execute(
            "UPDATE appointments SET status = ?, cancelled_at = datetime('now', 'localtime') "
            "WHERE id = ?",
            (STATUS_CANCELLED, appointment_id),
        )
        log_event(
            conn,
            "consulta_cancelada",
            "appointments",
            appointment_id,
            f"{appt.patient_name} {fmt_time(appt.start)} ({appt.duration} min)",
        )
        prof = _get_professional(conn, appt.professional_id)
        return scheduler.window_containing(
            prof, appt.day, list_appointments(conn, appt.day), appt.start, appt.end
        )


def _get_professional(conn: sqlite3.Connection, professional_id: int) -> Professional:
    row = conn.execute(
        "SELECT * FROM professionals WHERE id = ? AND active = 1", (int(professional_id),)
    ).fetchone()
    if row is None:
        raise ValidationError("Profissional não encontrado.")
    return _professional(row)


# ----------------------------------------------------------- lista de espera

def list_waiting(conn: sqlite3.Connection, status: str | None = None) -> list[WaitingEntry]:
    if status:
        rows = conn.execute(
            "SELECT * FROM waiting_list WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM waiting_list ORDER BY id").fetchall()
    return [_waiting(r) for r in rows]


def add_waiting(
    conn: sqlite3.Connection,
    patient_name: str,
    professional_ids: Iterable[int],
    duration: int,
    available_from: str,
    available_until: str,
    requested_on: date | str,
    notes: str = "",
) -> int:
    patient_name = validate_name(patient_name, "Nome do paciente")
    ids = sorted({int(i) for i in professional_ids})
    if not ids:
        raise ValidationError("Selecione ao menos um profissional.")
    duration = validate_duration(duration)
    start, end = parse_time(available_from), parse_time(available_until)
    validate_interval(start, end, "Disponibilidade")
    if end - start < duration:
        raise ValidationError("A disponibilidade do paciente é menor que a duração necessária.")
    requested = parse_date(requested_on)
    notes = " ".join(str(notes).split())
    if len(notes) > MAX_NOTES:
        raise ValidationError(f"Observação muito longa (máximo {MAX_NOTES} caracteres).")
    with transaction(conn):
        if requested > get_agenda_day(conn):
            raise ValidationError("A data de entrada na lista não pode ser posterior à agenda.")
        valid = set(professional_names(conn))
        if not set(ids) <= valid:
            raise ValidationError("Profissional inválido na seleção.")
        cur = conn.execute(
            "INSERT INTO waiting_list (patient_name, professional_ids, duration_min, "
            "available_from, available_until, requested_on, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                patient_name,
                ",".join(str(i) for i in ids),
                duration,
                fmt_time(start),
                fmt_time(end),
                requested.isoformat(),
                notes,
            ),
        )
        log_event(conn, "espera_cadastrada", "waiting_list", cur.lastrowid, patient_name)
    return cur.lastrowid


def remove_waiting(conn: sqlite3.Connection, waiting_id: int) -> None:
    with transaction(conn):
        cur = conn.execute(
            "UPDATE waiting_list SET status = ? WHERE id = ? AND status = ?",
            (WAIT_REMOVED, int(waiting_id), WAIT_ACTIVE),
        )
        if cur.rowcount == 0:
            raise ValidationError("Solicitação não encontrada ou já inativa.")
        log_event(conn, "espera_removida", "waiting_list", int(waiting_id), "")


# -------------------------------------------------------------- sugestões

def available_windows(conn: sqlite3.Connection) -> list[Window]:
    day = get_agenda_day(conn)
    appts = list_appointments(conn, day)
    windows: list[Window] = []
    for prof in list_professionals(conn):
        windows.extend(scheduler.free_windows(prof, day, appts))
    return windows


def evaluate_window(conn: sqlite3.Connection, window: Window) -> list[Evaluation]:
    return scheduler.evaluate_candidates(
        window,
        list_appointments(conn, window.day),
        list_waiting(conn, WAIT_ACTIVE),
        get_agenda_day(conn),
        professional_names(conn),
    )


def confirm_fit_in(
    conn: sqlite3.Connection, waiting_id: int, professional_id: int, start: int
) -> int:
    """Confirma o encaixe após revalidar a disponibilidade, em uma única transação."""
    with transaction(conn):
        day = get_agenda_day(conn)
        prof = _get_professional(conn, professional_id)
        row = conn.execute("SELECT * FROM waiting_list WHERE id = ?", (int(waiting_id),)).fetchone()
        if row is None:
            raise ValidationError("Solicitação da lista de espera não encontrada.")
        entry = _waiting(row)
        if not entry.is_active:
            raise ValidationError("Esta solicitação não está mais ativa na lista de espera.")

        appts = list_appointments(conn, day)
        window = scheduler.window_containing(prof, day, appts, start, start + entry.duration)
        if window is None:
            raise ValidationError("O horário não está mais livre. Atualize as sugestões.")
        ev = scheduler.evaluate_candidates(
            window, appts, [entry], day, {prof.id: prof.name}
        )[0]
        if not ev.eligible:
            raise ValidationError(ev.reasons[0])
        if ev.start != start:
            raise ValidationError("A disponibilidade mudou. Atualize as sugestões.")

        cur = conn.execute(
            "INSERT INTO appointments (patient_name, professional_id, day, start_time, "
            "duration_min, status, origin, replaces_id, waiting_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.patient_name,
                prof.id,
                day.isoformat(),
                fmt_time(start),
                entry.duration,
                STATUS_CONFIRMED,
                ORIGIN_FIT_IN,
                window.cancelled_appointment_id,
                entry.id,
            ),
        )
        conn.execute(
            "UPDATE waiting_list SET status = ? WHERE id = ?", (WAIT_SCHEDULED, entry.id)
        )
        log_event(
            conn,
            "encaixe_confirmado",
            "appointments",
            cur.lastrowid,
            f"{entry.patient_name} com {prof.name} às {fmt_time(start)} ({entry.duration} min)",
        )
    return cur.lastrowid


# --------------------------------------------------------------- dashboard

@dataclass
class DashboardStats:
    day: date
    total: int
    confirmed: int
    cancelled: int
    fit_ins: int
    waiting: int
    free_windows: int
    free_minutes: int
    occupancy: dict[int, float]


def dashboard_stats(conn: sqlite3.Connection) -> DashboardStats:
    day = get_agenda_day(conn)
    appts = list_appointments(conn, day)
    windows = available_windows(conn)
    occupancy = {}
    for prof in list_professionals(conn):
        booked = sum(a.duration for a in appts if a.is_active and a.professional_id == prof.id)
        occupancy[prof.id] = booked / max(prof.day_end - prof.day_start, 1)
    return DashboardStats(
        day=day,
        total=len(appts),
        confirmed=sum(a.is_active for a in appts),
        cancelled=sum(not a.is_active for a in appts),
        fit_ins=sum(a.is_active and a.origin == ORIGIN_FIT_IN for a in appts),
        waiting=len(list_waiting(conn, WAIT_ACTIVE)),
        free_windows=len(windows),
        free_minutes=sum(w.length for w in windows),
        occupancy=occupancy,
    )


# ---------------------------------------------------------------- importação

@dataclass(frozen=True)
class ImportRow:
    patient_name: str
    professional_name: str
    specialty: str
    start: int
    duration: int
    status: str


def replace_agenda(conn: sqlite3.Connection, day: date, rows: list[ImportRow]) -> dict:
    """Substitui a agenda do dia pelos dados importados, em uma única transação.

    Os profissionais passam a ser exatamente os do arquivo (máximo de três);
    profissionais ausentes são desativados, e a lista de espera é ajustada.
    """
    names = list(dict.fromkeys(r.professional_name for r in rows))
    if not names:
        raise ValidationError("O arquivo não contém consultas.")
    if len(names) > MAX_PROFESSIONALS:
        raise ValidationError(f"O arquivo tem {len(names)} profissionais; o limite é {MAX_PROFESSIONALS}.")

    with transaction(conn):
        ids: dict[str, int] = {}
        for name in names:
            own = [r for r in rows if r.professional_name == name]
            specialty = next((r.specialty for r in own if r.specialty), "")
            first = min(r.start for r in own)
            last = max(r.start + r.duration for r in own)
            existing = conn.execute(
                "SELECT * FROM professionals WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                start = min(parse_time(existing["day_start"]), first)
                end = max(parse_time(existing["day_end"]), last)
                conn.execute(
                    "UPDATE professionals SET active = 1, day_start = ?, day_end = ?, "
                    "specialty = CASE WHEN ? <> '' THEN ? ELSE specialty END WHERE id = ?",
                    (fmt_time(start), fmt_time(end), specialty, specialty, existing["id"]),
                )
                ids[name] = existing["id"]
            else:
                start = min(parse_time("08:00"), first)
                end = max(parse_time("18:00"), last)
                cur = conn.execute(
                    "INSERT INTO professionals (name, specialty, day_start, day_end) "
                    "VALUES (?, ?, ?, ?)",
                    (name, specialty, fmt_time(start), fmt_time(end)),
                )
                ids[name] = cur.lastrowid

        keep = set(ids.values())
        for row in conn.execute("SELECT id FROM professionals WHERE active = 1").fetchall():
            if row["id"] not in keep:
                conn.execute("UPDATE professionals SET active = 0 WHERE id = ?", (row["id"],))

        removed = conn.execute(
            "DELETE FROM appointments WHERE day = ?", (day.isoformat(),)
        ).rowcount
        for r in rows:
            conn.execute(
                "INSERT INTO appointments (patient_name, professional_id, day, start_time, "
                "duration_min, status, origin) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    r.patient_name,
                    ids[r.professional_name],
                    day.isoformat(),
                    fmt_time(r.start),
                    r.duration,
                    r.status,
                    ORIGIN_AGENDA,
                ),
            )

        # Ajusta a lista de espera aos profissionais ativos.
        dropped = 0
        for entry in list_waiting(conn, WAIT_ACTIVE):
            valid = [i for i in entry.professional_ids if i in keep]
            if not valid:
                conn.execute(
                    "UPDATE waiting_list SET status = ? WHERE id = ?", (WAIT_REMOVED, entry.id)
                )
                dropped += 1
            elif len(valid) != len(entry.professional_ids):
                conn.execute(
                    "UPDATE waiting_list SET professional_ids = ? WHERE id = ?",
                    (",".join(str(i) for i in valid), entry.id),
                )

        set_agenda_day(conn, day)
        log_event(
            conn,
            "agenda_importada",
            "appointments",
            None,
            f"{len(rows)} consultas para {day.isoformat()} ({removed} substituídas)",
        )
    return {"imported": len(rows), "replaced": removed, "waiting_removed": dropped}
