"""Modelos reproduzíveis; só são registrados quando o administrador solicitar."""
from __future__ import annotations
from dataclasses import dataclass
from authorization import Actor, Permission, require
from file_library import Storage, upload_asset
from services import _insert
from database import Database, transaction

@dataclass(frozen=True)
class TemplateSeed:
    title: str; description: str; category: str; template_type: str; filename: str; content: bytes

def _pdf(text: str) -> bytes:
    body = f"BT /F1 16 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    parts = [b"%PDF-1.4\n", b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n", b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n", b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n", b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n", b"5 0 obj<</Length "+str(len(body)).encode()+b">>stream\n"+body+b"\nendstream endobj\n"]
    return b"".join(parts)+b"xref\n0 1\n0000000000 65535 f\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n"

def default_templates() -> list[TemplateSeed]:
    return [
      TemplateSeed("Agenda de atendimentos", "Compatível com Importar / Exportar.", "agenda", "csv", "agenda_modelo.csv", b"data;horario;duracao_min;profissional;especialidade;paciente;status\n2026-01-01;08:00;30;Dra. Exemplo;Clinica Geral;Paciente Exemplo;confirmado\n"),
      TemplateSeed("Lista de espera", "Modelo de referência; importação ainda não disponível.", "lista_espera", "csv", "lista_espera_modelo.csv", b"paciente;profissionais;duracao_min;disponivel_de;disponivel_ate;observacao\nPaciente Exemplo;Dra. Exemplo;30;08:00;12:00;\n"),
      TemplateSeed("Profissionais", "Modelo de referência; importação ainda não disponível.", "profissionais", "csv", "profissionais_modelo.csv", b"nome;especialidade;inicio;fim\nDra. Exemplo;Clinica Geral;08:00;18:00\n"),
      TemplateSeed("Guia de preenchimento", "Guia para o CSV de agenda.", "guia", "pdf", "guia_importacao.pdf", _pdf("Guia de importacao Agende Bem")),
      TemplateSeed("Relatório diário", "Modelo de referência para resumo operacional.", "relatorio", "csv", "relatorio_diario_modelo.csv", b"data;atendimentos;cancelamentos;encaixes;ocupacao\n2026-01-01;0;0;0;0%\n"),
    ]

def register_defaults(conn: Database, storage: Storage, actor: Actor) -> int:
    require(actor, Permission.MANAGE_TEMPLATES)
    created = 0
    for seed in default_templates():
        if conn.execute("SELECT id FROM file_templates WHERE title = ?", (seed.title,)).fetchone(): continue
        asset = upload_asset(conn, storage, actor, seed.filename, seed.content, "application/pdf" if seed.template_type == "pdf" else "text/csv", "modelo")
        with transaction(conn):
            template_id = _insert(conn, "INSERT INTO file_templates (title, description, category, template_type, current_asset_id) VALUES (?, ?, ?, ?, ?)", (seed.title, seed.description, seed.category, seed.template_type, asset.id))
            conn.execute("INSERT INTO file_template_versions (template_id, version_number, asset_id, change_summary) VALUES (?, 1, ?, ?)", (template_id, asset.id, "Versão inicial"))
        created += 1
    return created
