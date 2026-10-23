"""Importação e exportação de agenda em CSV."""
from __future__ import annotations

import csv
import io
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

import services
from models import (
    Appointment,
    MAX_PROFESSIONALS,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    ValidationError,
    fmt_time,
    parse_date,
    parse_time,
    validate_duration,
    validate_name,
)

MAX_BYTES = 1_000_000  # 1 MB
MAX_ROWS = 500
REQUIRED_COLUMNS = ("data", "horario", "duracao_min", "profissional", "paciente")
OPTIONAL_COLUMNS = ("especialidade", "status")
EXPORT_COLUMNS = (
    "data", "horario", "fim", "duracao_min", "profissional", "especialidade",
    "paciente", "status", "origem",
)

_ALIASES = {
    "hora": "horario",
    "inicio": "horario",
    "duracao": "duracao_min",
    "duracao_minutos": "duracao_min",
    "medico": "profissional",
    "nome_paciente": "paciente",
}
_STATUS_ALIASES = {
    "": STATUS_CONFIRMED,
    "confirmado": STATUS_CONFIRMED,
    "confirmada": STATUS_CONFIRMED,
    "agendado": STATUS_CONFIRMED,
    "cancelado": STATUS_CANCELLED,
    "cancelada": STATUS_CANCELLED,
}
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class ParsedAgenda:
    day: date | None = None
    rows: list[services.ImportRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    preview: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.rows)


def _normalize_header(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    text = text.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
    return _ALIASES.get(text, text)


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("Não foi possível ler o arquivo. Salve-o como CSV UTF-8.")


def parse_agenda_csv(raw: bytes) -> ParsedAgenda:
    """Lê e valida o CSV sem gravar nada. Erros vêm com o número da linha."""
    result = ParsedAgenda()
    if len(raw) > MAX_BYTES:
        result.errors.append(f"Arquivo maior que o limite de {MAX_BYTES // 1000} KB.")
        return result
    if not raw.strip():
        result.errors.append("Arquivo vazio.")
        return result
    try:
        text = _decode(raw)
    except ValidationError as exc:
        result.errors.append(str(exc))
        return result

    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = [_normalize_header(h) for h in next(reader)]
    except (StopIteration, csv.Error):
        result.errors.append("Cabeçalho ausente ou inválido.")
        return result

    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        result.errors.append(
            "Colunas obrigatórias ausentes: " + ", ".join(missing)
            + ". Esperado: " + ", ".join(REQUIRED_COLUMNS) + "."
        )
        return result

    raw_rows = []
    try:
        for values in reader:
            if not any(v.strip() for v in values):
                continue
            raw_rows.append(dict(zip(header, (v.strip() for v in values))))
            if len(raw_rows) > MAX_ROWS:
                result.errors.append(f"O arquivo excede o limite de {MAX_ROWS} consultas.")
                return result
    except csv.Error as exc:
        result.errors.append(f"CSV malformado: {exc}.")
        return result

    if not raw_rows:
        result.errors.append("O arquivo não contém consultas.")
        return result

    result.preview = pd.DataFrame(raw_rows, columns=[c for c in header if c])
    result.preview.index = range(2, len(raw_rows) + 2)  # linha no arquivo
    result.preview.index.name = "linha"

    days: set[date] = set()
    professionals: dict[str, int] = {}
    pseudo_appointments: list[Appointment] = []

    for line, data in enumerate(raw_rows, start=2):
        try:
            day = parse_date(data.get("data", ""))
            start = parse_time(data.get("horario", ""))
            duration = validate_duration(data.get("duracao_min", ""))
            prof = validate_name(data.get("profissional", ""), "Profissional")
            patient = validate_name(data.get("paciente", ""), "Paciente")
            status_raw = data.get("status", "").strip().lower()
            if status_raw not in _STATUS_ALIASES:
                raise ValidationError(f"Status '{status_raw}' inválido (use confirmado ou cancelado).")
            if start + duration > 24 * 60:
                raise ValidationError("A consulta ultrapassa o fim do dia.")
            specialty = data.get("especialidade", "").strip()[:60]
            if specialty.startswith(_FORMULA_PREFIXES):
                raise ValidationError("Especialidade não pode começar com =, +, -, @.")
        except ValidationError as exc:
            result.errors.append(f"Linha {line}: {exc}")
            continue

        days.add(day)
        prof_key = professionals.setdefault(prof, len(professionals) + 1)
        status = _STATUS_ALIASES[status_raw]
        result.rows.append(services.ImportRow(patient, prof, specialty, start, duration, status))
        pseudo_appointments.append(Appointment(line, patient, prof_key, day, start, duration, status))

    if len(days) > 1:
        listed = ", ".join(sorted(d.strftime("%d/%m/%Y") for d in days))
        result.errors.append(f"O arquivo deve conter um único dia de atendimento (encontrado: {listed}).")
    if len(professionals) > MAX_PROFESSIONALS:
        result.errors.append(
            f"O arquivo tem {len(professionals)} profissionais; o limite é {MAX_PROFESSIONALS}."
        )
    result.errors.extend(services.find_overlaps(pseudo_appointments))
    result.day = next(iter(days)) if len(days) == 1 else None
    return result


def import_agenda(conn: sqlite3.Connection, parsed: ParsedAgenda) -> dict:
    if not parsed.ok or parsed.day is None:
        raise ValidationError("Corrija as inconsistências antes de importar.")
    return services.replace_agenda(conn, parsed.day, parsed.rows)


def sanitize_cell(value) -> str:
    """Neutraliza fórmulas para evitar CSV Injection ao abrir no Excel/Sheets."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def export_agenda_csv(conn: sqlite3.Connection) -> bytes:
    """Exporta a agenda do dia (inclui cancelamentos e encaixes) em CSV ';' UTF-8."""
    day = services.get_agenda_day(conn)
    profs = {p.id: p for p in services.list_professionals(conn)}
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(EXPORT_COLUMNS)
    for appt in sorted(services.list_appointments(conn, day), key=lambda a: (a.professional_id, a.start)):
        prof = profs.get(appt.professional_id)
        writer.writerow(
            sanitize_cell(v)
            for v in (
                appt.day.isoformat(),
                fmt_time(appt.start),
                fmt_time(appt.end),
                appt.duration,
                prof.name if prof else "",
                prof.specialty if prof else "",
                appt.patient_name,
                appt.status,
                appt.origin,
            )
        )
    return buffer.getvalue().encode("utf-8-sig")
