"""Smoke test da interface: todas as telas renderizam sem exceção e o fluxo principal funciona."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["Dashboard", "Agenda", "Lista de espera", "Sugestões", "Importar / Exportar"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENDE_BEM_DB", str(tmp_path / "ui.db"))
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_all_pages_render(app):
    for page in PAGES:
        app.radio(key="page").set_value(page).run()
        assert not app.exception, page


def test_cancel_suggest_confirm_flow(app):
    app.radio(key="page").set_value("Agenda").run()
    cancel = next(b for b in app.button if b.label == "Cancelar" and b.key == "cancel_4")  # Marcos Vieira
    cancel.click().run()
    app.button(key="confirm_4").click().run()
    assert not app.exception
    assert app.session_state["page"] == "Sugestões"
    assert any("cancelada" in s.value for s in app.success)

    pick = next(b for b in app.button if b.label == "Selecionar")
    pick.click().run()
    next(b for b in app.button if b.label == "Confirmar encaixe").click().run()
    assert not app.exception
    assert app.session_state["page"] == "Agenda"
    assert any("Paula Andrade" in s.value for s in app.success)
