"""Smoke test da interface: todas as telas renderizam sem exceção e o fluxo principal funciona."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DEMO_DAY
from database import connect
from seed import reset_demo

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["Dashboard", "Agenda", "Lista de espera", "Sugestões", "Aproveitamento", "Histórico", "Apresentação", "Importar / Exportar"]


@pytest.fixture
def app(tmp_path, monkeypatch, backend, request):
    if backend == "sqlite":
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("AGENDE_BEM_DB", str(tmp_path / "ui.db"))
    else:
        monkeypatch.setenv("DATABASE_URL", request.getfixturevalue("pg_urls")[1])
        reset_demo(connect(), DEMO_DAY)
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_all_pages_render(app):
    for page in PAGES:
        slug = {
            "Dashboard": "dashboard",
            "Agenda": "agenda",
            "Lista de espera": "espera",
            "Sugestões": "sugestoes",
            "Aproveitamento": "aproveitamento",
            "Histórico": "historico",
            "Apresentação": "apresentacao",
            "Importar / Exportar": "dados",
        }[page]
        app.button(key=f"nav_{slug}").click().run()
        assert not app.exception, page


def test_cancel_suggest_confirm_flow(app):
    app.button(key="nav_agenda").click().run()
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


def test_import_by_pasted_csv(app):
    sample = (Path(APP).parent / "samples" / "agenda_exemplo.csv").read_text(encoding="utf-8")
    app.button(key="nav_dados").click().run()
    app.text_area(key="pasted_0").set_value(sample).run()
    assert not app.error
    next(b for b in app.button if b.label == "Importar agenda").click().run()
    assert not app.exception
    assert any("22 consultas" in s.value for s in app.success)
