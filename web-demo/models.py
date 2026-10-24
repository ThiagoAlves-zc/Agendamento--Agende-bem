"""Modelos de domínio e validações essenciais do Agende Bem.

Horários são representados internamente em minutos desde 00:00 (int),
o que simplifica comparações de intervalos. Datas usam ``datetime.date``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
MAX_PROFESSIONALS = 3
MIN_DURATION = 10
MAX_DURATION = 240
DURATION_STEP = 5
DAY_MINUTES = 24 * 60

STATUS_CONFIRMED = "confirmado"
STATUS_CANCELLED = "cancelado"
APPOINTMENT_STATUSES = (STATUS_CONFIRMED, STATUS_CANCELLED)

ORIGIN_AGENDA = "agenda"
ORIGIN_FIT_IN = "encaixe"

WAIT_ACTIVE = "ativo"
WAIT_SCHEDULED = "encaixado"
WAIT_REMOVED = "removido"

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
# Letras (inclusive acentuadas), espaços, ponto, apóstrofo e hífen internos.
_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .'\-]{1,79}$")


class ValidationError(ValueError):
    """Erro de regra de negócio com mensagem pronta para a interface."""


# ---------------------------------------------------------------- conversões

def parse_time(value: str) -> int:
    """Converte 'HH:MM' em minutos desde 00:00."""
    text = str(value).strip()
    match = _TIME_RE.match(text)
    if not match:
        raise ValidationError(f"Horário inválido: '{text}'. Use o formato HH:MM.")
    return int(match.group(1)) * 60 + int(match.group(2))


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_date(value: str | date) -> date:
    """Aceita AAAA-MM-DD ou DD/MM/AAAA."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValidationError(f"Data inválida: '{text}'. Use AAAA-MM-DD ou DD/MM/AAAA.")


def fmt_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def today_local() -> date:
    """Data de hoje no fuso da clínica (o servidor pode rodar em UTC)."""
    return datetime.now(LOCAL_TZ).date()


# --------------------------------------------------------------- validações

def validate_name(value: str, label: str = "Nome") -> str:
    text = " ".join(str(value).split())
    if not _NAME_RE.match(text):
        raise ValidationError(
            f"{label} inválido: use de 2 a 80 caracteres, apenas letras, espaços, "
            "ponto, apóstrofo ou hífen."
        )
    return text


def validate_duration(value) -> int:
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"Duração inválida: '{value}'. Informe minutos inteiros.")
    if not MIN_DURATION <= minutes <= MAX_DURATION or minutes % DURATION_STEP:
        raise ValidationError(
            f"Duração inválida: {minutes} min. Use valores entre {MIN_DURATION} e "
            f"{MAX_DURATION} minutos, em múltiplos de {DURATION_STEP}."
        )
    return minutes


def validate_interval(start: int, end: int, label: str = "Intervalo") -> None:
    if not 0 <= start < end <= DAY_MINUTES:
        raise ValidationError(f"{label} inválido: o início deve ser anterior ao fim.")


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


# ------------------------------------------------------------------ modelos

@dataclass(frozen=True)
class Professional:
    id: int
    name: str
    specialty: str
    day_start: int
    day_end: int


@dataclass(frozen=True)
class Appointment:
    id: int
    patient_name: str
    professional_id: int
    day: date
    start: int
    duration: int
    status: str = STATUS_CONFIRMED
    origin: str = ORIGIN_AGENDA

    @property
    def end(self) -> int:
        return self.start + self.duration

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_CONFIRMED


@dataclass(frozen=True)
class WaitingEntry:
    id: int
    patient_name: str
    professional_ids: tuple[int, ...]
    duration: int
    available_from: int
    available_until: int
    requested_on: date
    status: str = WAIT_ACTIVE
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == WAIT_ACTIVE


@dataclass(frozen=True)
class Window:
    """Intervalo livre na agenda de um profissional."""

    professional_id: int
    day: date
    start: int
    end: int
    cancelled_appointment_id: int | None = None

    @property
    def length(self) -> int:
        return self.end - self.start

    def label(self) -> str:
        return f"{fmt_time(self.start)}–{fmt_time(self.end)} ({self.length} min)"


@dataclass
class Evaluation:
    """Resultado da análise de um candidato da lista de espera para uma janela."""

    entry: WaitingEntry
    eligible: bool
    start: int | None = None
    wait_days: int = 0
    leftover: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def end(self) -> int | None:
        return None if self.start is None else self.start + self.entry.duration

    @property
    def occupancy(self) -> float:
        total = self.entry.duration + self.leftover
        return self.entry.duration / total if total else 0.0
