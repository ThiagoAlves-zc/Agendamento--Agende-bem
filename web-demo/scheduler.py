"""Motor de encaixe do Agende Bem.

Funções puras, sem acesso a banco ou interface, para facilitar testes.

Um candidato só é elegível para uma janela livre quando:
1. o profissional da janela está entre os aceitos pelo paciente;
2. a duração cabe integralmente no intervalo liberado;
3. o paciente está disponível no horário proposto;
4. não há conflito com outra consulta (do profissional ou do paciente);
5. a solicitação está ativa na lista de espera;
6. o atendimento ocorre no mesmo dia da agenda.

Elegíveis são ordenados por: maior tempo de espera (em dias), melhor
aproveitamento do intervalo (menor sobra) e ordem de cadastro.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping

from models import (
    Appointment,
    Evaluation,
    MIN_DURATION,
    Professional,
    WaitingEntry,
    Window,
    fmt_time,
    overlaps,
)


def free_windows(
    professional: Professional,
    day: date,
    appointments: Iterable[Appointment],
    min_length: int = MIN_DURATION,
) -> list[Window]:
    """Lista os intervalos livres do profissional dentro do expediente."""
    own = [a for a in appointments if a.professional_id == professional.id and a.day == day]
    active = sorted((a for a in own if a.is_active), key=lambda a: a.start)
    cancelled = sorted((a for a in own if not a.is_active), key=lambda a: a.id, reverse=True)

    gaps: list[tuple[int, int]] = []
    cursor = professional.day_start
    for appt in active:
        if appt.start > cursor:
            gaps.append((cursor, min(appt.start, professional.day_end)))
        cursor = max(cursor, appt.end)
    if cursor < professional.day_end:
        gaps.append((cursor, professional.day_end))

    windows = []
    for start, end in gaps:
        if end - start < min_length:
            continue
        # Associa a janela ao cancelamento mais recente contido nela, se houver.
        source = next(
            (c.id for c in cancelled if overlaps(start, end, c.start, c.end)), None
        )
        windows.append(Window(professional.id, day, start, end, source))
    return windows


def window_containing(
    professional: Professional,
    day: date,
    appointments: Iterable[Appointment],
    start: int,
    end: int | None = None,
) -> Window | None:
    """Retorna a janela livre que contém o intervalo [start, end)."""
    end = start + 1 if end is None else end
    for window in free_windows(professional, day, appointments, min_length=1):
        if window.start <= start and end <= window.end:
            return window
    return None


def _plural_days(days: int) -> str:
    if days <= 0:
        return "Entrou na lista de espera hoje"
    return f"Aguarda há {days} dia{'s' if days != 1 else ''} na lista de espera"


def evaluate_candidates(
    window: Window,
    appointments: Iterable[Appointment],
    waiting_list: Iterable[WaitingEntry],
    agenda_day: date,
    professional_names: Mapping[int, str] | None = None,
) -> list[Evaluation]:
    """Avalia todos os candidatos: elegíveis (ordenados) seguidos dos recusados."""
    names = professional_names or {}
    prof_name = names.get(window.professional_id, "o profissional")
    appts = [a for a in appointments if a.is_active and a.day == window.day]

    eligible: list[Evaluation] = []
    rejected: list[Evaluation] = []

    for entry in waiting_list:
        ev = Evaluation(entry=entry, eligible=False)

        if not entry.is_active:
            ev.reasons.append(f"Solicitação não está ativa (status: {entry.status}).")
        elif window.day != agenda_day:
            ev.reasons.append("O horário liberado não é do dia de atendimento atual.")
        elif window.professional_id not in entry.professional_ids:
            ev.reasons.append(f"Não aceita atendimento com {prof_name}.")
        elif entry.duration > window.length:
            ev.reasons.append(
                f"Precisa de {entry.duration} min, mas o horário livre tem {window.length} min."
            )
        else:
            start = max(window.start, entry.available_from)
            end = start + entry.duration
            limit = min(window.end, entry.available_until)
            if end > limit:
                ev.reasons.append(
                    f"Disponível apenas das {fmt_time(entry.available_from)} às "
                    f"{fmt_time(entry.available_until)}, fora do horário livre."
                )
            else:
                conflict = _find_conflict(appts, window.professional_id, entry, start, end)
                if conflict:
                    ev.reasons.append(conflict)
                else:
                    ev.eligible = True
                    ev.start = start
                    ev.wait_days = max((agenda_day - entry.requested_on).days, 0)
                    ev.leftover = window.length - entry.duration
                    ev.reasons.extend(_eligible_reasons(ev, window, prof_name))

        (eligible if ev.eligible else rejected).append(ev)

    eligible.sort(key=lambda e: (-e.wait_days, e.leftover, e.entry.id))
    return eligible + rejected


def suggest(
    window: Window,
    appointments: Iterable[Appointment],
    waiting_list: Iterable[WaitingEntry],
    agenda_day: date,
    professional_names: Mapping[int, str] | None = None,
) -> list[Evaluation]:
    """Somente os candidatos elegíveis, já ordenados."""
    return [
        ev
        for ev in evaluate_candidates(
            window, appointments, waiting_list, agenda_day, professional_names
        )
        if ev.eligible
    ]


def _find_conflict(
    appts: list[Appointment], professional_id: int, entry: WaitingEntry, start: int, end: int
) -> str | None:
    patient = entry.patient_name.casefold()
    for appt in appts:
        if not overlaps(start, end, appt.start, appt.end):
            continue
        if appt.professional_id == professional_id:
            return (
                f"Conflito com a consulta de {fmt_time(appt.start)}–{fmt_time(appt.end)} "
                "do mesmo profissional."
            )
        if appt.patient_name.casefold() == patient:
            return (
                f"Paciente já tem consulta das {fmt_time(appt.start)} às "
                f"{fmt_time(appt.end)} com outro profissional."
            )
    return None


def _eligible_reasons(ev: Evaluation, window: Window, prof_name: str) -> list[str]:
    entry = ev.entry
    pct = round(ev.occupancy * 100)
    usage = f"Consulta de {entry.duration} min ocupa {pct}% do horário livre de {window.length} min"
    usage += "." if ev.leftover == 0 else f" (sobram {ev.leftover} min)."
    return [
        _plural_days(ev.wait_days) + ".",
        f"Aceita atendimento com {prof_name}.",
        usage,
        f"Disponível das {fmt_time(entry.available_from)} às "
        f"{fmt_time(entry.available_until)}; encaixe às {fmt_time(ev.start)}–{fmt_time(ev.end)}.",
        "Sem conflito com outras consultas do dia.",
    ]
