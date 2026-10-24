import pytest

import services
import database
from models import ValidationError, parse_time


def find(conn, patient):
    return next(a for a in services.list_appointments(conn) if a.patient_name == patient)


def test_seed_scenario(conn):
    stats = services.dashboard_stats(conn)
    assert len(services.list_professionals(conn)) == 3
    assert stats.total == 19 and stats.cancelled == 0
    assert stats.waiting == 7
    assert {a.duration for a in services.list_appointments(conn)} == {20, 30, 45}


def test_cancel_preserves_record_and_suggests(conn):
    marcos = find(conn, "Marcos Vieira")
    window = services.cancel_appointment(conn, marcos.id)
    assert (window.start, window.end) == (parse_time("09:30"), parse_time("10:00"))
    assert window.cancelled_appointment_id == marcos.id
    assert find(conn, "Marcos Vieira").status == "cancelado"

    evals = services.evaluate_window(conn, window)
    eligible = [e.entry.patient_name for e in evals if e.eligible]
    assert eligible == ["Paula Andrade", "Gabriel Moreira", "Juliana Freitas"]
    rejected = {e.entry.patient_name: e.reasons[0] for e in evals if not e.eligible}
    assert "Precisa de 45 min" in rejected["Ricardo Sampaio"]
    assert "Não aceita" in rejected["Camila Ferraz"]
    assert "Disponível apenas" in rejected["Diego Carvalho"]
    assert "outro profissional" in rejected["Thiago Barros"]

    with pytest.raises(ValidationError):
        services.cancel_appointment(conn, marcos.id)


def test_confirm_fit_in_updates_agenda_waiting_and_audit(conn):
    window = services.cancel_appointment(conn, find(conn, "Marcos Vieira").id)
    best = services.evaluate_window(conn, window)[0]
    new_id = services.confirm_fit_in(conn, best.entry.id, window.professional_id, best.start)

    paula = find(conn, "Paula Andrade")
    assert paula.id == new_id and paula.origin == "encaixe" and paula.start == parse_time("09:30")
    assert all(e.patient_name != "Paula Andrade" for e in services.list_waiting(conn, "ativo"))
    assert services.recent_events(conn)[0]["event_type"] == "encaixe_confirmado"

    # Revalidação: o mesmo horário não pode ser preenchido duas vezes.
    gabriel = next(e for e in services.list_waiting(conn, "ativo") if e.patient_name == "Gabriel Moreira")
    with pytest.raises(ValidationError):
        services.confirm_fit_in(conn, gabriel.id, window.professional_id, best.start)
    assert services.dashboard_stats(conn).confirmed == 19


def test_confirm_rejects_inactive_or_incompatible(conn):
    window = services.cancel_appointment(conn, find(conn, "Marcos Vieira").id)
    ricardo = next(e for e in services.list_waiting(conn) if e.patient_name == "Ricardo Sampaio")
    before = len(services.list_appointments(conn))
    with pytest.raises(ValidationError):
        services.confirm_fit_in(conn, ricardo.id, window.professional_id, window.start)
    services.remove_waiting(conn, ricardo.id)
    with pytest.raises(ValidationError):
        services.confirm_fit_in(conn, ricardo.id, window.professional_id, window.start)
    assert len(services.list_appointments(conn)) == before


def test_professional_limit(conn):
    with pytest.raises(ValidationError, match="Limite"):
        services.add_professional(conn, "Dr. Quarto Nome", "Ortopedia", "08:00", "12:00")


def test_create_appointment_blocks_overlap_and_out_of_hours(conn):
    helena = services.list_professionals(conn)[0]
    with pytest.raises(ValidationError, match="Sobreposição"):
        services.create_appointment(conn, "Nova Pessoa", helena.id, "09:10", 30)
    with pytest.raises(ValidationError, match="expediente"):
        services.create_appointment(conn, "Nova Pessoa", helena.id, "11:50", 30)
    new_id = services.create_appointment(conn, "Nova Pessoa", helena.id, "11:35", 20)
    assert find(conn, "Nova Pessoa").id == new_id


@pytest.mark.parametrize("name", ["=CMD()", "+55", "@x", "A", "Nome<script>"])
def test_waiting_rejects_invalid_names(conn, name):
    with pytest.raises(ValidationError):
        services.add_waiting(conn, name, [1], 30, "08:00", "12:00", "2026-10-20")


def test_waiting_validations(conn):
    with pytest.raises(ValidationError, match="menor que a duração"):
        services.add_waiting(conn, "Lia Souza", [1], 45, "08:00", "08:30", "2026-10-20")
    with pytest.raises(ValidationError, match="ao menos um"):
        services.add_waiting(conn, "Lia Souza", [], 30, "08:00", "12:00", "2026-10-20")
    with pytest.raises(ValidationError, match="Duração"):
        services.add_waiting(conn, "Lia Souza", [1], 7, "08:00", "12:00", "2026-10-20")
    with pytest.raises(ValidationError, match="inválido"):
        services.add_waiting(conn, "Lia Souza", [99], 30, "08:00", "12:00", "2026-10-20")
    new_id = services.add_waiting(conn, "Lia Souza", [1, 2], 30, "08:00", "12:00", "2026-10-20")
    assert any(e.id == new_id for e in services.list_waiting(conn, "ativo"))


def test_data_persists_across_connections(conn, open_db, backend):
    services.cancel_appointment(conn, find(conn, "Marcos Vieira").id)
    conn.close()
    if backend == "postgres":
        database.close_pools()  # simula reinício da instância: nenhum estado em memória
    reopened = open_db()
    assert find(reopened, "Marcos Vieira").status == "cancelado"
    reopened.close()
