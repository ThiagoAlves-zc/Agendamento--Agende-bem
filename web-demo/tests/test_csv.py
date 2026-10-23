from pathlib import Path

import csv_handler
import services

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
HEADER = "data;horario;duracao_min;profissional;paciente\n"


def test_sample_csv_is_valid():
    parsed = csv_handler.parse_agenda_csv((SAMPLES / "agenda_exemplo.csv").read_bytes())
    assert parsed.ok, parsed.errors
    assert len(parsed.rows) == 22
    assert parsed.day.isoformat() == "2026-10-23"


def test_error_sample_reports_line_numbers():
    parsed = csv_handler.parse_agenda_csv((SAMPLES / "agenda_com_erros.csv").read_bytes())
    text = "\n".join(parsed.errors)
    assert not parsed.ok
    assert "Linha 4: Horário inválido" in text
    assert "Linha 5: Duração inválida" in text
    assert "Linha 6: Paciente inválido" in text  # tentativa de fórmula
    assert "Linha 7: Status" in text
    assert "único dia" in text
    assert "Sobreposição" in text


def test_limits():
    assert csv_handler.parse_agenda_csv(b"x" * (csv_handler.MAX_BYTES + 1)).errors
    rows = "".join(
        f"2026-10-23;{8 + i:02d}:00;30;Dr. Nome {chr(65 + i)};Paciente {chr(65 + i)}\n" for i in range(4)
    )
    errors = csv_handler.parse_agenda_csv((HEADER + rows).encode()).errors
    assert any("limite é 3" in e for e in errors)
    assert csv_handler.parse_agenda_csv(b"a;b\n1;2\n").errors[0].startswith("Colunas obrigatórias")


def test_comma_separator_and_br_date():
    raw = "data,horario,duracao_min,profissional,paciente\n23/10/2026,08:00,30,Dra. Ana,Bia Lopes\n"
    parsed = csv_handler.parse_agenda_csv(raw.encode())
    assert parsed.ok and parsed.day.isoformat() == "2026-10-23"


def test_sanitize_cell():
    for value in ("=1+1", "+55", "-2", "@SUM(A1)", "\tx"):
        assert csv_handler.sanitize_cell(value).startswith("'")
    assert csv_handler.sanitize_cell("Ana") == "Ana"


def test_import_replaces_agenda_and_keeps_waiting_list(conn):
    parsed = csv_handler.parse_agenda_csv((SAMPLES / "agenda_exemplo.csv").read_bytes())
    result = csv_handler.import_agenda(conn, parsed)
    assert result["imported"] == 22 and result["waiting_removed"] == 0
    stats = services.dashboard_stats(conn)
    assert stats.total == 22 and stats.cancelled == 1 and stats.waiting == 7


def test_import_new_professionals_deactivates_old_and_adjusts_waiting(conn):
    raw = HEADER + (
        "2026-10-24;08:00;30;Dra. Helena Prado;Ana Souza\n"
        "2026-10-24;08:00;30;Dr. Novo Nome;Caio Lima\n"
    )
    result = csv_handler.import_agenda(conn, csv_handler.parse_agenda_csv(raw.encode()))
    names = [p.name for p in services.list_professionals(conn)]
    assert names == ["Dra. Helena Prado", "Dr. Novo Nome"]
    assert services.get_agenda_day(conn).isoformat() == "2026-10-24"
    assert result["waiting_removed"] == 1  # Camila só aceitava a Dra. Lívia


def test_export_round_trip(conn):
    marcos = next(a for a in services.list_appointments(conn) if a.patient_name == "Marcos Vieira")
    services.cancel_appointment(conn, marcos.id)
    data = csv_handler.export_agenda_csv(conn)
    assert data.startswith(b"\xef\xbb\xbf")
    assert "Marcos Vieira;cancelado" in data.decode("utf-8-sig")
    parsed = csv_handler.parse_agenda_csv(data)
    assert parsed.ok and len(parsed.rows) == 19
