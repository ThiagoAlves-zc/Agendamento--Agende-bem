"""Agende Bem — Agenda Inteligente (interface Streamlit).

Execute com:  streamlit run app.py
"""
from __future__ import annotations

import base64
from datetime import time as dtime
from datetime import timedelta
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import csv_handler
import scheduler
import services
from database import DatabaseError, connect
from models import (
    ORIGIN_FIT_IN,
    STATUS_CANCELLED,
    WAIT_ACTIVE,
    ValidationError,
    Window,
    fmt_date_br,
    fmt_time,
)
from seed import ensure_seeded, reset_demo

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_CSV = BASE_DIR / "samples" / "agenda_exemplo.csv"

PAGES = ["Dashboard", "Agenda", "Lista de espera", "Sugestões", "Aproveitamento", "Histórico", "Apresentação", "Importar / Exportar"]
PAGE_SLUGS = dict(zip(PAGES, ["dashboard", "agenda", "espera", "sugestoes", "aproveitamento", "historico", "apresentacao", "dados"]))
PAGE_SLUGS_REVERSE = {slug: page for page, slug in PAGE_SLUGS.items()}
WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

st.set_page_config(
    page_title="Agende Bem — Agenda Inteligente",
    page_icon=":material/event_available:",
    layout="wide",
    # Em telas estreitas, o modo automático preserva o conteúdo e mantém o menu no controle nativo.
    initial_sidebar_state="auto",
)


# ------------------------------------------------------------------ infra

def db():
    """Nova conexão por execução: o SQLite não deve ser compartilhado entre threads."""
    return connect()


def flash(kind: str, message: str) -> None:
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flash() -> None:
    icons = {"success": ":material/check_circle:", "error": ":material/error:",
             "warning": ":material/warning:", "info": ":material/info:"}
    for kind, message in st.session_state.pop("flash", []):
        getattr(st, kind)(message, icon=icons[kind])


def go(page: str) -> None:
    st.session_state.page = page
    st.query_params["pagina"] = PAGE_SLUGS[page]


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def page_head(eyebrow: str, title: str, subtitle: str, selected_day=None) -> None:
    date_markup = ""
    if selected_day is not None:
        date_markup = (
            '<div class="ab-head-date"><span>Data selecionada</span>'
            f'<b>{escape(day_label(selected_day))}</b></div>'
        )
    html(
        f'<div class="ab-page-head"><div><div class="ab-eyebrow">{escape(eyebrow)}</div>'
        f'<div class="ab-title">{escape(title)}</div>'
        f'<div class="ab-subtitle">{escape(subtitle)}</div></div>{date_markup}</div>'
    )


def badge(appt) -> str:
    if appt.status == STATUS_CANCELLED:
        return '<span class="ab-badge cancel">Cancelado</span>'
    if appt.origin == ORIGIN_FIT_IN:
        return '<span class="ab-badge fit">Encaixe</span>'
    return '<span class="ab-badge ok">Confirmado</span>'


def day_label(day) -> str:
    return f"{WEEKDAYS[day.weekday()].capitalize()}, {fmt_date_br(day)}"


def window_key(window: Window) -> tuple[int, int]:
    return (window.professional_id, window.start)


# -------------------------------------------------------------- callbacks

def on_confirm_cancel(appointment_id: int, patient: str) -> None:
    try:
        window = services.cancel_appointment(db(), appointment_id)
    except ValidationError as exc:
        flash("error", str(exc))
        return
    flash("success", f"Consulta de {patient} cancelada. O registro original foi preservado.")
    if window is not None:
        st.session_state.focus_window = window_key(window)
        st.session_state.pop("selected_candidate", None)
        go("Sugestões")


def on_open_suggestions(key: tuple[int, int]) -> None:
    st.session_state.focus_window = key
    go("Sugestões")


def on_confirm_fit_in(waiting_id: int, professional_id: int, start: int, patient: str) -> None:
    try:
        services.confirm_fit_in(db(), waiting_id, professional_id, start)
    except ValidationError as exc:
        flash("error", f"Encaixe não confirmado: {exc}")
        return
    st.session_state.fit_success = {
        "patient": patient,
        "professional_id": professional_id,
        "start": start,
    }
    # O marcador na URL mantém um estado de conclusão visível após uma reconexão.
    st.query_params["encaixe"] = "confirmado"
    flash("success", f"Encaixe confirmado: {patient} às {fmt_time(start)}. Agenda e lista de espera atualizadas.")
    st.session_state.pop("focus_window", None)
    st.session_state.agenda_tab_hint = professional_id
    go("Agenda")


def on_reset_demo() -> None:
    reset_demo(db())
    for key in ("pending_cancel", "selected_candidate", "focus_window", "confirm_reset"):
        st.session_state.pop(key, None)
    st.session_state.uploader_round = st.session_state.get("uploader_round", 0) + 1
    flash("success", "Dados de demonstração restaurados.")
    go("Dashboard")


def on_export() -> None:
    conn = db()
    services.log_event(conn, "agenda_exportada", "appointments", None, "CSV exportado")


def on_close_fit_success() -> None:
    st.session_state.pop("fit_success", None)
    st.query_params.pop("encaixe", None)


@st.dialog("Cancelar atendimento")
def cancel_dialog(appt) -> None:
    """Confirmação explícita: abrir/fechar o diálogo não altera a agenda."""
    st.markdown(f"Você está prestes a cancelar o atendimento de **{appt.patient_name}**.")
    c1, c2 = st.columns(2)
    c1.metric("Horário", f"{fmt_time(appt.start)}–{fmt_time(appt.end)}")
    c2.metric("Duração", f"{appt.duration} min")
    st.warning("O atendimento continuará no histórico com o status Cancelado.", icon=":material/warning:")
    back, confirm = st.columns(2)
    back.button("Voltar", key=f"back_{appt.id}", width="stretch")
    confirm.button("Cancelar atendimento", key=f"confirm_{appt.id}", type="primary",
                   on_click=on_confirm_cancel, args=(appt.id, appt.patient_name), width="stretch")


@st.dialog("Confirmar encaixe")
def fit_in_dialog(ev, professional_id: int, professional_name: str) -> None:
    """Resumo antes da confirmação; o serviço revalida transacionalmente ao gravar."""
    st.markdown(f"Confirme o encaixe de **{ev.entry.patient_name}** na agenda.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Profissional", professional_name)
    c2.metric("Horário", f"{fmt_time(ev.start)}–{fmt_time(ev.end)}")
    c3.metric("Duração", f"{ev.entry.duration} min")
    st.markdown("**Critérios atendidos**")
    for reason in ev.reasons:
        st.markdown(f"- {reason}")
    st.caption("A disponibilidade será revalidada em transação antes de salvar.")
    back, confirm = st.columns(2)
    back.button("Voltar", key=f"undo_{ev.entry.id}", width="stretch")
    confirm.button("Confirmar encaixe", key=f"confirm_fit_{ev.entry.id}", type="primary",
                   on_click=on_confirm_fit_in,
                   args=(ev.entry.id, professional_id, ev.start, ev.entry.patient_name), width="stretch")


# ---------------------------------------------------------------- sidebar

def sidebar(conn) -> str:
    with st.sidebar:
        html(
            '<div class="ab-brand"><div class="ab-logo">AB</div><div>'
            '<div class="ab-brand-name">Agende Bem</div>'
            '<div class="ab-brand-tag">Agenda Inteligente</div></div></div>'
        )
        html('<div class="ab-nav-label">Navegação</div>')
        page = st.session_state.page
        navigation = [
            ("dashboard", "Dashboard", ":material/dashboard:"),
            ("agenda", "Agenda", ":material/calendar_month:"),
            ("espera", "Lista de Espera", ":material/group:"),
            ("sugestoes", "Central de encaixes", ":material/event_available:"),
            ("aproveitamento", "Aproveitamento", ":material/insights:"),
            ("historico", "Histórico", ":material/history:"),
            ("apresentacao", "Modo de apresentação", ":material/slideshow:"),
            ("dados", "Importar / Exportar", ":material/import_export:"),
        ]
        for slug, label, icon in navigation:
            target = PAGE_SLUGS_REVERSE[slug]
            st.button(f"{icon}  {label}", key=f"nav_{slug}", width="stretch",
                      type="primary" if page == target else "secondary", on_click=go, args=(target,))
        day = services.get_agenda_day(conn)
        html('<div class="ab-side-label">Dia de atendimento</div>'
             f'<div class="ab-side-date">{escape(day_label(day))}</div>')
        html('<div class="ab-side-label">Demonstração</div>')
        with st.expander("Restaurar dados de demonstração"):
            st.caption("Recarrega o cenário fictício e descarta as alterações deste banco. "
                       "Arquivos externos não são afetados.")
            confirmed = st.checkbox("Confirmo a restauração", key="confirm_reset")
            st.button("Restaurar agora", on_click=on_reset_demo, disabled=not confirmed,
                      width="stretch")
        html('<div class="ab-side-foot">Ambiente de demonstração.<br>'
             'Todos os dados são fictícios.</div>')
    return page


# -------------------------------------------------------------- dashboard

def page_dashboard(conn) -> None:
    stats = services.dashboard_stats(conn)
    profs = services.list_professionals(conn)
    page_head("Central operacional", "Bom trabalho, recepção",
              "Priorize os próximos atendimentos e resolva oportunidades de encaixe do dia.", stats.day)

    cards = [
        ("", "Atendimentos", stats.total, f"{len(profs)} profissionais", "●"),
        ("green", "Confirmados", stats.confirmed, f"{stats.fit_ins} por encaixe", "✓"),
        ("amber", "Em espera", stats.waiting, "pacientes aguardando", "◷"),
        ("cyan", "Horários livres", stats.free_windows, f"{stats.free_minutes} min livres", "○"),
    ]
    html('<div class="ab-metrics">' + "".join(
        f'<div class="ab-metric {cls}"><div class="ab-metric-top"><div class="ab-metric-label">{escape(label)}</div>'
        f'<span class="ab-metric-icon" aria-hidden="true">{icon}</span></div>'
        f'<div class="ab-metric-value">{value}</div><div class="ab-metric-note">{escape(note)}</div></div>'
        for cls, label, value, note, icon in cards
    ) + "</div>")

    # Destaque: horários liberados por cancelamento com candidatos compatíveis.
    opportunities = []
    for window in services.available_windows(conn):
        if window.cancelled_appointment_id is None:
            continue
        eligible = [e for e in services.evaluate_window(conn, window) if e.eligible]
        if eligible:
            opportunities.append((window, len(eligible)))
    if opportunities:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
            names = services.professional_names(conn)
            text = "; ".join(f"{names.get(w.professional_id, '')} às {fmt_time(w.start)} ({n} candidato{'s' if n > 1 else ''})"
                             for w, n in opportunities)
            c1.markdown(f"**{len(opportunities)} horário(s) liberado(s) com encaixe possível** — {text}")
            c2.button("Ver sugestões", type="primary", width="stretch",
                      on_click=on_open_suggestions, args=(window_key(opportunities[0][0]),))

    left, right = st.columns([1.3, 1])
    with left:
        rows = []
        for prof in profs:
            pct = stats.occupancy.get(prof.id, 0)
            rows.append(
                f'<div class="ab-bar-row"><div class="ab-bar-head"><span><b>{escape(prof.name)}</b> · '
                f'{escape(prof.specialty)}</span><span>{pct:.0%} ocupado · {fmt_time(prof.day_start)}–'
                f'{fmt_time(prof.day_end)}</span></div><div class="ab-bar"><div style="width:{min(pct, 1) * 100:.0f}%">'
                '</div></div></div>'
            )
        html('<div class="ab-panel"><div class="ab-panel-title">Ocupação por profissional</div>'
             + "".join(rows) + "</div>")
    with right:
        events = services.recent_events(conn, 7)
        labels = {
            "consulta_cancelada": "Cancelamento", "encaixe_confirmado": "Encaixe",
            "espera_cadastrada": "Lista de espera", "espera_removida": "Lista de espera",
            "agenda_importada": "Importação", "agenda_exportada": "Exportação",
            "dados_demo_restaurados": "Sistema", "consulta_criada": "Agenda",
            "profissional_cadastrado": "Profissional",
        }
        items = "".join(
            f'<div class="ab-event"><span class="ab-event-time">{escape(e["created_at"][11:16])}</span>'
            f'<span><b>{escape(labels.get(e["event_type"], e["event_type"]))}</b> '
            f'{escape(e["details"])}</span></div>'
            for e in events
        ) or '<div class="ab-slot-meta">Nenhuma atividade registrada.</div>'
        html(f'<div class="ab-panel"><div class="ab-panel-title">Atividade recente</div>{items}</div>')

    appts = sorted((a for a in services.list_appointments(conn, stats.day) if a.is_active), key=lambda a: a.start)
    names = services.professional_names(conn)
    upcoming = appts[:4]
    lower_left, lower_right = st.columns([1.45, 1], gap="medium")
    with lower_left:
        rows = "".join(
            f'<div class="ab-next"><b>{fmt_time(a.start)}</b><span>{escape(a.patient_name)}</span>'
            f'<small>{escape(names.get(a.professional_id, "—"))} · {a.duration} min</small></div>'
            for a in upcoming
        ) or '<div class="ab-slot-meta">Não há atendimentos confirmados neste dia.</div>'
        html(f'<div class="ab-panel"><div class="ab-panel-title">Próximos atendimentos</div>{rows}</div>')
    with lower_right:
        with st.container(border=True):
            st.markdown("**Ações rápidas**")
            st.caption("Acesse os fluxos operacionais sem sair do contexto do dia.")
            c1, c2 = st.columns(2)
            c1.button("Abrir agenda", key="dash_agenda", on_click=go, args=("Agenda",), width="stretch")
            c2.button("Ver encaixes", key="dash_fits", on_click=go, args=("Sugestões",), width="stretch", type="primary")


# ------------------------------------------------------------------ agenda

def timeline_html(prof, appts, windows) -> str:
    items = [(a.start, 0, a) for a in appts] + [(w.start, 1, w) for w in windows]
    parts = []
    for _, kind, item in sorted(items, key=lambda x: (x[0], x[1])):
        if kind == 1:
            parts.append(
                f'<div class="ab-slot free"><div class="ab-slot-top"><span class="ab-slot-time">'
                f'{fmt_time(item.start)}–{fmt_time(item.end)}</span><span class="ab-badge free">Livre</span></div>'
                f'<div class="ab-slot-name">Horário livre</div>'
                f'<div class="ab-slot-meta">{item.length} min disponíveis</div></div>'
            )
            continue
        cls = "cancelled" if item.status == STATUS_CANCELLED else ("fitin" if item.origin == ORIGIN_FIT_IN else "")
        parts.append(
            f'<div class="ab-slot {cls}"><div class="ab-slot-top"><span class="ab-slot-time">'
            f'{fmt_time(item.start)}–{fmt_time(item.end)}</span>{badge(item)}</div>'
            f'<div class="ab-slot-name">{escape(item.patient_name)}</div>'
            f'<div class="ab-slot-meta">{item.duration} min</div></div>'
        )
    return (
        f'<div class="ab-col-head"><b>{escape(prof.name)}</b><span>{escape(prof.specialty)} · '
        f'{fmt_time(prof.day_start)}–{fmt_time(prof.day_end)}</span></div>'
        f'<div class="ab-col-body">{"".join(parts) or "<div class=ab-slot-meta>Sem consultas.</div>"}</div>'
    )


def page_agenda(conn) -> None:
    day = services.get_agenda_day(conn)
    profs = services.list_professionals(conn)
    appts = services.list_appointments(conn, day)
    page_head("Agenda do dia", "Agenda por profissional",
              "Visualize atendimentos, vagas e cancelamentos por profissional.", day)
    st.caption("**Linha do tempo** · blocos proporcionais representam a duração. Use as abas para a lista detalhada e acessível.")

    if st.query_params.get("encaixe") == "confirmado":
        success = st.session_state.get("fit_success")
        names = services.professional_names(conn)
        if success:
            detail = (f"{success['patient']} foi incluído(a) às {fmt_time(success['start'])} "
                      f"com {names.get(success['professional_id'], 'o profissional selecionado')}.")
        else:
            detail = "O último encaixe foi salvo. A agenda abaixo já reflete a atualização."
        with st.container(border=True):
            st.success(f"Encaixe confirmado. {detail}", icon=":material/check_circle:")
            c1, c2 = st.columns(2)
            c1.button("Continuar na agenda", key="close_fit_success", on_click=on_close_fit_success,
                      width="stretch")
            c2.button("Ir para exportação", key="success_export", on_click=go,
                      args=("Importar / Exportar",), width="stretch")

    hint = st.session_state.pop("agenda_tab_hint", None)
    if hint:
        name = next((p.name for p in profs if p.id == hint), "")
        st.caption(f"O novo encaixe aparece destacado em ciano na coluna de {name}.")

    tabs = st.tabs(["Visão geral"] + [p.name for p in profs])
    with tabs[0]:
        cols = st.columns(len(profs) or 1)
        for col, prof in zip(cols, profs):
            own = [a for a in appts if a.professional_id == prof.id]
            with col:
                html(timeline_html(prof, own, scheduler.free_windows(prof, day, appts, min_length=5)))
        st.caption("Para cancelar, abra a aba do profissional.")

    for tab, prof in zip(tabs[1:], profs):
        with tab:
            own = sorted((a for a in appts if a.professional_id == prof.id), key=lambda a: (a.start, a.id))
            if not own:
                st.info("Nenhuma consulta para este profissional.")
            for appt in own:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.3, 3, 1.3, 1.6], vertical_alignment="center")
                    c1.markdown(f"**{fmt_time(appt.start)}–{fmt_time(appt.end)}**")
                    c2.markdown(f"{appt.patient_name}  \n:gray[{appt.duration} min]")
                    with c3:
                        html(badge(appt))
                    if appt.status == STATUS_CANCELLED:
                        continue
                    if c4.button("Cancelar", key=f"cancel_{appt.id}", width="stretch"):
                        cancel_dialog(appt)

    active = [a for a in appts if a.is_active]
    if active:
        detail_names = services.professional_names(conn)
        detail = st.selectbox(
            "Detalhes do atendimento",
            active,
            format_func=lambda a: f"{fmt_time(a.start)} · {a.patient_name} · {detail_names.get(a.professional_id, '—')}",
            key="agenda_detail",
        )
        with st.container(border=True):
            st.markdown(f"**{detail.patient_name}** · {fmt_time(detail.start)}–{fmt_time(detail.end)}")
            st.caption(f"{detail.duration} min · {'Encaixe confirmado' if detail.origin == ORIGIN_FIT_IN else 'Atendimento confirmado'}")


# --------------------------------------------------------- lista de espera

def page_waiting(conn) -> None:
    day = services.get_agenda_day(conn)
    profs = services.list_professionals(conn)
    names = {p.id: p.name for p in profs}
    page_head("Lista de espera", "Pacientes aguardando encaixe",
              "Cadastre quem aceita ser chamado caso um horário seja liberado.", day)

    left, right = st.columns([1, 2.4], gap="medium")
    with left:
        with st.form("waiting_form", clear_on_submit=True):
            st.markdown("**Novo paciente na espera**")
            patient = st.text_input("Nome do paciente", max_chars=80, placeholder="Ex.: Maria Oliveira")
            chosen = st.multiselect("Profissionais aceitos", options=list(names),
                                    format_func=lambda i: names[i], placeholder="Selecione um ou mais")
            duration = st.number_input("Duração necessária (min)", min_value=10, max_value=240,
                                       value=30, step=5)
            c1, c2 = st.columns(2)
            start = c1.time_input("Disponível a partir de", value=dtime(8, 0), step=timedelta(minutes=5))
            end = c2.time_input("Disponível até", value=dtime(12, 0), step=timedelta(minutes=5))
            since = st.date_input("Na lista desde", value=day, max_value=day, format="DD/MM/YYYY")
            notes = st.text_input("Observação (opcional)", max_chars=200,
                                  help="Não registre dados clínicos, CPF ou diagnósticos.")
            submitted = st.form_submit_button("Adicionar à lista", type="primary", width="stretch")
        if submitted:
            try:
                services.add_waiting(conn, patient, chosen, duration, start.strftime("%H:%M"),
                                     end.strftime("%H:%M"), since, notes)
            except ValidationError as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                flash("success", f"{patient.strip()} adicionado(a) à lista de espera.")
                st.rerun()

    with right:
        f1, f2 = st.columns([1.5, 1])
        search = f1.text_input("Pesquisar paciente", key="waiting_search", placeholder="Nome, profissional ou situação")
        selected_prof = f2.selectbox("Profissional", [None] + list(names), format_func=lambda i: "Todos" if i is None else names[i], key="waiting_professional")
        only_active = st.segmented_control("Situação", ["Ativos", "Todos"], default="Ativos",
                                           label_visibility="collapsed") != "Todos"
        entries = services.list_waiting(conn, WAIT_ACTIVE if only_active else None)
        if selected_prof is not None:
            entries = [e for e in entries if selected_prof in e.professional_ids]
        if search.strip():
            term = search.casefold().strip()
            entries = [e for e in entries if term in e.patient_name.casefold()
                       or term in e.status.casefold()
                       or any(term in names.get(prof_id, "").casefold() for prof_id in e.professional_ids)]
        entries.sort(key=lambda e: (day - e.requested_on).days, reverse=True)
        st.caption(f"{len([e for e in entries if e.status == WAIT_ACTIVE])} paciente(s) ativo(s) nesta visão · ordenado por tempo de espera.")
        if not entries:
            st.info("Nenhum paciente corresponde à pesquisa." if search.strip()
                    else "Nenhum paciente na lista de espera.")
            return
        table = pd.DataFrame([
            {
                "Ordem": e.id,
                "Paciente": e.patient_name,
                "Profissionais": ", ".join(names.get(i, "—") for i in e.professional_ids),
                "Duração": f"{e.duration} min",
                "Disponibilidade": f"{fmt_time(e.available_from)}–{fmt_time(e.available_until)}",
                "Espera": f"{max((day - e.requested_on).days, 0)} dias",
                "Status": e.status.capitalize(),
                "Observação": e.notes,
            }
            for e in entries
        ])
        st.dataframe(table, hide_index=True, width="stretch")

        active = [e for e in entries if e.status == WAIT_ACTIVE]
        if active:
            with st.expander("Remover paciente da lista"):
                target = st.selectbox("Paciente", active, format_func=lambda e: f"#{e.id} · {e.patient_name}")
                if st.button("Remover da lista"):
                    services.remove_waiting(conn, target.id)
                    flash("info", f"{target.patient_name} removido(a) da lista de espera.")
                    st.rerun()


# --------------------------------------------------------------- sugestões

def page_suggestions(conn) -> None:
    day = services.get_agenda_day(conn)
    names = services.professional_names(conn)
    appts = {a.id: a for a in services.list_appointments(conn, day)}
    page_head("Central de encaixes", "Oportunidades para horários livres",
              "Candidatos são ordenados por regras determinísticas; a recepção confirma cada encaixe.", day)

    windows = services.available_windows(conn)
    if not windows:
        st.info("Não há horários livres na agenda. Cancele uma consulta para liberar um horário.")
        return

    def label(w: Window) -> str:
        text = f"{names.get(w.professional_id, '')} · {w.label()}"
        source = appts.get(w.cancelled_appointment_id)
        return text + (f" · liberado pelo cancelamento de {source.patient_name}" if source else " · horário vago")

    windows.sort(key=lambda w: (w.cancelled_appointment_id is None, w.professional_id, w.start))
    keys = [window_key(w) for w in windows]
    focus = st.session_state.get("focus_window")
    index = keys.index(focus) if focus in keys else 0
    window = st.selectbox("Horário liberado", windows, index=index, format_func=label)
    st.session_state.focus_window = window_key(window)

    source = appts.get(window.cancelled_appointment_id)
    html(
        '<div class="ab-window">'
        f'<div><small>Profissional</small><b>{escape(names.get(window.professional_id, ""))}</b></div>'
        f'<div><small>Horário livre</small><b>{fmt_time(window.start)}–{fmt_time(window.end)}</b></div>'
        f'<div><small>Duração</small><b>{window.length} min</b></div>'
        f'<div><small>Origem</small><b>{escape("Cancelamento de " + source.patient_name if source else "Horário vago")}</b></div>'
        '</div>'
    )

    evaluations = services.evaluate_window(conn, window)
    eligible = [e for e in evaluations if e.eligible]
    rejected = [e for e in evaluations if not e.eligible]
    st.markdown(f"#### {len(eligible)} candidato(s) elegível(is)")
    if not eligible:
        st.warning("Nenhum paciente da lista de espera atende a este horário. Veja os motivos abaixo.",
                   icon=":material/warning:")

    for rank, ev in enumerate(eligible, start=1):
        args = (ev.entry.id, window.professional_id, ev.start)
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.4], vertical_alignment="top")
            with c1:
                tag = '<span class="ab-badge fit">Melhor opção</span>' if rank == 1 else ""
                reasons = "".join(f"<li>{escape(r)}</li>" for r in ev.reasons)
                html(
                    f'<div class="ab-cand-head"><span class="ab-rank {"top" if rank == 1 else ""}">{rank}</span>'
                    f'<span class="ab-cand-name">{escape(ev.entry.patient_name)}</span>'
                    f'<span class="ab-badge ok">{fmt_time(ev.start)}–{fmt_time(ev.end)}</span>'
                    f'<span class="ab-badge free">Espera: {ev.wait_days} dias</span>'
                    f'<span class="ab-badge free">Aproveitamento: {ev.occupancy:.0%}</span>{tag}</div>'
                    f'<ul class="ab-reasons">{reasons}</ul>'
                    f'<div class="ab-candidate-meta">Duração necessária: {ev.entry.duration} min · '
                    f'Disponível: {fmt_time(ev.entry.available_from)}–{fmt_time(ev.entry.available_until)}</div>'
                )
            with c2:
                if st.button("Selecionar", key=f"pick_{ev.entry.id}", width="stretch",
                             type="primary" if rank == 1 else "secondary"):
                    fit_in_dialog(ev, window.professional_id, names.get(window.professional_id, ""))

    if rejected:
        with st.expander(f"Candidatos não elegíveis ({len(rejected)})"):
            st.dataframe(
                pd.DataFrame([{"Paciente": e.entry.patient_name, "Motivo": e.reasons[0]} for e in rejected]),
                hide_index=True, width="stretch",
            )


# ---------------------------------------------------- visões operacionais

def page_utilization(conn) -> None:
    day = services.get_agenda_day(conn)
    summary = services.utilization_summary(conn)
    page_head("Operação", "Visão de aproveitamento",
              "Indicadores calculados exclusivamente a partir da agenda persistida.", day)
    cards = [
        ("Vagas abertas", summary.open_windows, f"{summary.open_minutes} min disponíveis"),
        ("Encaixes confirmados", summary.fit_in_count, f"{summary.recovered_minutes} min recuperados"),
        ("Taxa de ocupação", f"{summary.occupancy_rate:.0%}", "consultas ativas / capacidade"),
    ]
    html('<div class="ab-operation-metrics">' + ''.join(
        f'<div class="ab-operation-card"><span>{escape(label)}</span><b>{value}</b><small>{escape(note)}</small></div>'
        for label, value, note in cards
    ) + '</div>')
    with st.container(border=True):
        st.markdown("**Como calculamos**")
        st.markdown(
            "- **Vagas abertas:** intervalos livres identificados dentro do expediente cadastrado.\n"
            "- **Tempo recuperado:** soma das durações de atendimentos ativos com origem `encaixe`.\n"
            "- **Taxa de ocupação:** minutos de consultas ativas ÷ minutos totais de expediente dos profissionais ativos."
        )


def page_history(conn) -> None:
    day = services.get_agenda_day(conn)
    page_head("Rastreabilidade", "Histórico de atividades",
              "Registro das operações realizadas neste ambiente de demonstração.", day)
    labels = {
        "consulta_cancelada": "Consulta cancelada", "encaixe_confirmado": "Encaixe confirmado",
        "espera_cadastrada": "Entrada na lista de espera", "espera_removida": "Saída da lista de espera",
        "agenda_importada": "Agenda importada", "agenda_exportada": "Agenda exportada",
        "dados_demo_restaurados": "Dados restaurados", "consulta_criada": "Consulta criada",
        "profissional_cadastrado": "Profissional cadastrado",
    }
    events = services.activity_history(conn)
    search = st.text_input("Pesquisar no histórico", placeholder="Operação ou descrição", key="history_search")
    if search.strip():
        term = search.casefold().strip()
        events = [e for e in events if term in e["event_type"].casefold() or term in e["details"].casefold()]
    table = pd.DataFrame([
        {
            "Data e hora": e["created_at"].replace("T", " ")[:16],
            "Operação": labels.get(e["event_type"], e["event_type"].replace("_", " ").capitalize()),
            "Descrição": e["details"] or "—",
        }
        for e in events
    ])
    if table.empty:
        st.info("Nenhum evento corresponde à pesquisa.")
    else:
        st.dataframe(table, hide_index=True, width="stretch", height=480)


def page_presentation(conn) -> None:
    day = services.get_agenda_day(conn)
    page_head("Demonstração", "Fluxo guiado de encaixe",
              "Use dados sintéticos e confirme cada operação manualmente durante a apresentação.", day)
    steps = [
        ("1", "Abra a agenda", "Encontre um atendimento confirmado e selecione Cancelar."),
        ("2", "Revise o cancelamento", "O modal preserva o histórico e requer confirmação explícita."),
        ("3", "Analise candidatos", "A Central de encaixes explica elegibilidade e ordenação."),
        ("4", "Confirme o encaixe", "A disponibilidade é revalidada transacionalmente antes de gravar."),
        ("5", "Confira a agenda", "O novo atendimento aparece com origem de encaixe.")
    ]
    html('<div class="ab-demo-steps">' + ''.join(
        f'<div class="ab-demo-step"><b>{n}</b><div><strong>{escape(title)}</strong><span>{escape(text)}</span></div></div>'
        for n, title, text in steps
    ) + '</div>')
    c1, c2 = st.columns(2)
    c1.button("Começar pela agenda", type="primary", width="stretch", on_click=go, args=("Agenda",))
    c2.button("Abrir central de encaixes", width="stretch", on_click=go, args=("Sugestões",))
    st.caption("Este modo não reinicializa dados nem executa cancelamentos ou encaixes automaticamente.")


# ------------------------------------------------------- importar/exportar

def page_import_export(conn) -> None:
    day = services.get_agenda_day(conn)
    page_head("Dados", "Importar e exportar agenda",
              "Importe um CSV de um único dia (até 3 profissionais) ou exporte a agenda atualizada.", day)
    imp, exp = st.tabs(["Importar CSV", "Exportar agenda"])

    with imp:
        st.markdown(
            "Colunas obrigatórias: `data`, `horario`, `duracao_min`, `profissional`, `paciente`. "
            "Opcionais: `especialidade`, `status` (confirmado/cancelado). Separador `;` ou `,`. "
            f"Limite de {csv_handler.MAX_BYTES // 1000} KB e {csv_handler.MAX_ROWS} linhas."
        )
        st.download_button("Baixar modelo CSV", SAMPLE_CSV.read_bytes(), file_name="agenda_exemplo.csv",
                           mime="text/csv", on_click="ignore")
        upload_round = st.session_state.get("uploader_round", 0)
        uploaded = st.file_uploader("Arquivo CSV da agenda", type=["csv"], key=f"uploader_{upload_round}")
        # Alternativa ao upload HTTP: o texto segue pela conexão WebSocket já aberta, útil quando
        # a hospedagem distribui requisições entre instâncias (ex.: containers na Vercel).
        with st.expander("Alternativa: colar o conteúdo do CSV"):
            pasted = st.text_area("Conteúdo do CSV", height=160, max_chars=csv_handler.MAX_BYTES,
                                  key=f"pasted_{upload_round}",
                                  placeholder="data;horario;duracao_min;profissional;especialidade;paciente;status")
        raw = uploaded.getvalue() if uploaded is not None else (pasted.encode("utf-8") if pasted.strip() else None)
        if raw is not None:
            parsed = csv_handler.parse_agenda_csv(raw)
            if parsed.rows or parsed.day:
                m1, m2, m3 = st.columns(3)
                m1.metric("Dia", fmt_date_br(parsed.day) if parsed.day else "—")
                m2.metric("Consultas válidas", len(parsed.rows))
                m3.metric("Profissionais", len({r.professional_name for r in parsed.rows}))
            if parsed.errors:
                st.error("**Inconsistências encontradas — corrija o arquivo e envie novamente:**\n\n"
                         + "\n".join(f"- {e}" for e in parsed.errors[:30]), icon=":material/error:")
            if not parsed.preview.empty:
                st.markdown("**Prévia do arquivo**")
                st.dataframe(parsed.preview, width="stretch", height=280)
            if parsed.ok:
                current = len(services.list_appointments(conn, parsed.day))
                st.warning(f"A importação substituirá a agenda de {fmt_date_br(parsed.day)} "
                           f"({current} consulta(s) atuais) e definirá os profissionais do arquivo.",
                           icon=":material/warning:")
                if st.button("Importar agenda", type="primary"):
                    try:
                        result = csv_handler.import_agenda(conn, parsed)
                    except ValidationError as exc:
                        st.error(str(exc))
                    else:
                        msg = f"Agenda importada: {result['imported']} consultas."
                        if result["waiting_removed"]:
                            msg += f" {result['waiting_removed']} solicitação(ões) da espera foram desativadas."
                        flash("success", msg)
                        st.session_state.uploader_round = st.session_state.get("uploader_round", 0) + 1
                        st.rerun()

    with exp:
        names = services.professional_names(conn)
        appts = services.list_appointments(conn, day)
        st.dataframe(
            pd.DataFrame([
                {"Horário": f"{fmt_time(a.start)}–{fmt_time(a.end)}", "Profissional": names.get(a.professional_id, ""),
                 "Paciente": a.patient_name, "Duração": f"{a.duration} min", "Status": a.status.capitalize(),
                 "Origem": a.origin.capitalize()}
                for a in sorted(appts, key=lambda a: (a.professional_id, a.start))
            ]),
            hide_index=True, width="stretch", height=360,
        )
        export_bytes = csv_handler.export_agenda_csv(conn)
        export_name = f"agenda_agende_bem_{day.isoformat()}.csv"
        st.download_button(
            "Exportar agenda (CSV)", export_bytes, file_name=export_name, mime="text/csv",
            type="primary", on_click=on_export,
        )
        # Link embutido (data URI): não depende do armazenamento em memória de uma instância.
        encoded = base64.b64encode(export_bytes).decode("ascii")
        html(f'<a class="ab-alt-download" download="{escape(export_name)}" '
             f'href="data:text/csv;charset=utf-8;base64,{encoded}">Link alternativo de download</a>')
        st.caption("O arquivo usa `;` como separador e UTF-8, compatível com Excel. Células que "
                   "começam com =, +, - ou @ são neutralizadas contra CSV Injection.")


# -------------------------------------------------------------------- main

def main() -> None:
    html(f"<style>{(BASE_DIR / 'styles.css').read_text(encoding='utf-8')}</style>")
    # A página fica na URL: se o WebSocket reconectar em outra instância, a tela é mantida.
    if "page" not in st.session_state:
        st.session_state.page = PAGE_SLUGS_REVERSE.get(st.query_params.get("pagina", ""), PAGES[0])
    try:
        conn = db()
        ensure_seeded(conn)
    except DatabaseError as exc:
        st.error(f"Banco de dados indisponível: {exc}", icon=":material/error:")
        st.stop()
    except Exception as exc:  # falha de rede/pool: não expor detalhes de conexão na tela
        print(f"[agende-bem] falha ao conectar ao banco: {type(exc).__name__}", flush=True)
        st.error("Não foi possível conectar ao banco de dados. Tente novamente em instantes.",
                 icon=":material/error:")
        st.stop()
    page = sidebar(conn)
    if st.query_params.get("pagina") != PAGE_SLUGS[page]:
        st.query_params["pagina"] = PAGE_SLUGS[page]
    show_flash()
    {
        "Dashboard": page_dashboard,
        "Agenda": page_agenda,
        "Lista de espera": page_waiting,
        "Sugestões": page_suggestions,
        "Aproveitamento": page_utilization,
        "Histórico": page_history,
        "Apresentação": page_presentation,
        "Importar / Exportar": page_import_export,
    }[page](conn)


main()
