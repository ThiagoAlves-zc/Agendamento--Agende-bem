from datetime import date, timedelta

from models import Appointment, Professional, WaitingEntry, Window, parse_time
from scheduler import evaluate_candidates, free_windows, suggest, window_containing

DAY = date(2026, 10, 23)
PROF = Professional(1, "Dra. Ana", "Clínica", parse_time("08:00"), parse_time("12:00"))


def appt(i, start, dur, prof=1, patient=None, status="confirmado"):
    return Appointment(i, patient or f"Paciente {i}", prof, DAY, parse_time(start), dur, status)


def entry(i, dur=30, profs=(1,), frm="08:00", until="12:00", waited=5, status="ativo", name=None):
    return WaitingEntry(i, name or f"Espera {i}", tuple(profs), dur, parse_time(frm),
                        parse_time(until), DAY - timedelta(days=waited), status)


AGENDA = [appt(1, "08:00", 30), appt(2, "08:30", 30, status="cancelado"), appt(3, "09:00", 60)]
WINDOW = Window(1, DAY, parse_time("08:30"), parse_time("09:00"), 2)


def test_free_windows_include_cancelled_slot_and_end_of_day():
    windows = free_windows(PROF, DAY, AGENDA)
    assert [(w.start, w.end) for w in windows] == [(510, 540), (600, 720)]
    assert windows[0].cancelled_appointment_id == 2
    assert windows[1].cancelled_appointment_id is None


def test_window_containing():
    assert window_containing(PROF, DAY, AGENDA, 510, 540).start == 510
    assert window_containing(PROF, DAY, AGENDA, 480, 510) is None


def test_ranking_wait_then_fit_then_registration_order():
    candidates = [
        entry(1, dur=20, waited=10),
        entry(2, dur=30, waited=10),  # mesma espera, melhor aproveitamento
        entry(3, dur=30, waited=3),
        entry(4, dur=30, waited=10),  # empata com 2, cadastrado depois
    ]
    ranked = suggest(WINDOW, AGENDA, candidates, DAY)
    assert [e.entry.id for e in ranked] == [2, 4, 1, 3]
    assert ranked[0].leftover == 0 and ranked[0].occupancy == 1.0
    assert any("Aguarda há 10 dias" in r for r in ranked[0].reasons)


def test_rules_reject_with_reason():
    candidates = [
        entry(1, profs=(2,)),          # profissional incompatível
        entry(2, dur=45),              # não cabe no intervalo
        entry(3, frm="10:00"),         # indisponível no horário
        entry(4, status="encaixado"),  # solicitação inativa
        entry(5, name="Paciente 3"),   # já tem consulta às 09:00, sem sobreposição
    ]
    evals = {e.entry.id: e for e in evaluate_candidates(WINDOW, AGENDA, candidates, DAY)}
    assert "Não aceita" in evals[1].reasons[0]
    assert "Precisa de 45 min" in evals[2].reasons[0]
    assert "Disponível apenas" in evals[3].reasons[0]
    assert "não está ativa" in evals[4].reasons[0]
    assert evals[5].eligible
    assert not any(evals[i].eligible for i in (1, 2, 3, 4))


def test_patient_conflict_with_other_professional():
    other = appt(9, "08:30", 30, prof=2, patient="Bia Lopes")
    evals = evaluate_candidates(WINDOW, AGENDA + [other], [entry(1, name="bia lopes")], DAY)
    assert not evals[0].eligible
    assert "outro profissional" in evals[0].reasons[0]


def test_late_availability_shifts_start_inside_window():
    window = Window(1, DAY, parse_time("10:00"), parse_time("12:00"))
    ev = suggest(window, AGENDA, [entry(1, dur=30, frm="11:00")], DAY)[0]
    assert ev.start == parse_time("11:00") and ev.end == parse_time("11:30")


def test_window_must_be_on_agenda_day():
    evals = evaluate_candidates(WINDOW, AGENDA, [entry(1)], DAY + timedelta(days=1))
    assert not evals[0].eligible
    assert "dia de atendimento" in evals[0].reasons[0]


def test_today_local_uses_clinic_timezone(monkeypatch):
    """O servidor roda em UTC; a data da agenda deve seguir America/Sao_Paulo."""
    from datetime import datetime, timezone

    import models

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            utc = datetime(2026, 10, 24, 1, 30, tzinfo=timezone.utc)  # 22:30 do dia 23 em Brasília
            return utc.astimezone(tz) if tz else utc

    monkeypatch.setattr(models, "datetime", FakeDatetime)
    assert models.today_local() == date(2026, 10, 23)
