# Agende Bem — Agenda Inteligente (MVP web)

Aplicação web local para a recepção de uma clínica. Quando um paciente cancela,
o sistema identifica candidatos compatíveis na lista de espera e **sugere** encaixes;
a recepção confirma manualmente.

Esta pasta é independente da versão original de terminal (`../projeto final entrega/`),
que não foi alterada. Não há conexão com o MySQL antigo nem reaproveitamento de credenciais.

## Stack

Python 3.11+ (imagem de produção: 3.14) · Streamlit · SQLite ou PostgreSQL · Pandas · Pytest.

## Como executar

```bash
cd web-demo
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py
```

Acesse **http://localhost:8501**. O servidor escuta apenas em `localhost`
(ver `.streamlit/config.toml`).

Na primeira execução o banco `data/agende_bem.db` é criado e carregado com dados
fictícios. Os dados persistem entre reinicializações.

- Restaurar o cenário: barra lateral → *Restaurar dados de demonstração* (com confirmação),
  ou `python seed.py`.
- Testes: `python -m pytest -q`.

## Banco de dados

- **Local (padrão):** SQLite em `data/agende_bem.db`, migrations aplicadas automaticamente.
- **Remoto:** defina `DATABASE_URL` (PostgreSQL/Supabase, TLS obrigatório). As migrations
  ficam em `migrations/postgres/` e são aplicadas pelo operador com `migrate.py`.
  Guia completo de implantação (Vercel + Supabase): [DEPLOY.md](DEPLOY.md).

Testes no PostgreSQL (banco descartável, criado do zero pelo próprio teste):

```bash
pip install -r requirements-dev.txt
TEST_PG_ADMIN_URL=postgresql://postgres@127.0.0.1:55432/postgres python -m pytest -q
```

## Telas

| Tela | O que faz |
|---|---|
| Dashboard | Data, total, confirmados, cancelamentos, pacientes em espera, horários livres, ocupação e atividade recente |
| Agenda | Visão geral lado a lado e abas por profissional; cancelamento com confirmação em duas etapas |
| Lista de espera | Cadastro (profissionais aceitos, duração, disponibilidade) e listagem/remoção |
| Sugestões | Horário liberado, candidatos elegíveis ordenados com justificativa, confirmação manual, motivos dos não elegíveis |
| Importar / Exportar | Upload de CSV com validação e prévia; exportação da agenda atualizada |

## Motor de encaixe (`scheduler.py`)

Função pura `evaluate_candidates(janela, agenda, lista_de_espera, dia)`.
Um candidato é elegível quando: o profissional é compatível; a duração cabe no intervalo;
o paciente está disponível; não há conflito com outra consulta (do profissional ou do próprio
paciente); a solicitação está ativa; e o horário é do dia da agenda.

Ordenação: **1)** mais dias de espera, **2)** melhor aproveitamento do intervalo (menor sobra),
**3)** ordem de cadastro. Ao confirmar, `services.confirm_fit_in` revalida tudo dentro de uma
transação SQLite (`BEGIN IMMEDIATE`) antes de gravar.

## Formato do CSV

Separador `;` ou `,`, UTF-8. Um único dia, no máximo 3 profissionais, até 500 linhas e 1 MB.

```
data;horario;duracao_min;profissional;especialidade;paciente;status
2026-10-23;09:30;30;Dra. Helena Prado;Clínica Geral;Marcos Vieira;confirmado
```

Obrigatórias: `data` (AAAA-MM-DD ou DD/MM/AAAA), `horario` (HH:MM), `duracao_min`
(10–240, múltiplos de 5), `profissional`, `paciente`. Opcionais: `especialidade`, `status`.
A importação substitui a agenda daquele dia e define os profissionais do arquivo.

Exemplos: `samples/agenda_exemplo.csv` (válido) e `samples/agenda_com_erros.csv`
(para demonstrar as mensagens de inconsistência).

## Segurança e privacidade

- Apenas dados sintéticos; sem CPF, diagnóstico ou dados clínicos (nomes são validados).
- Todas as consultas SQL são parametrizadas.
- Exportação protegida contra CSV Injection (células iniciadas por `= + - @` são neutralizadas).
- Limites de tamanho/linhas no upload; validação de horários, durações, sobreposições e limite de 3 profissionais.
- Sem login: esta versão **não** oferece controle de acesso e deve rodar apenas em máquina controlada.
- Telemetria do Streamlit desativada; nenhum dado é enviado para fora.

## Roteiro de apresentação (≈5 min)

1. **Dashboard** — mostre os indicadores do dia (19 atendimentos, 7 pacientes em espera).
2. **Agenda** — visão dos 3 profissionais, com horários livres tracejados.
3. **Importar / Exportar** — envie `agenda_com_erros.csv` para mostrar a validação; depois
   `agenda_exemplo.csv` e clique em *Importar agenda*.
4. **Lista de espera** — mostre os candidatos e cadastre um novo paciente.
5. **Agenda → aba Dra. Helena Prado** — cancele *Marcos Vieira, 09:30 (30 min)* e confirme.
6. O sistema abre **Sugestões** automaticamente: Paula Andrade em 1º (12 dias de espera, 100% do
   intervalo), Gabriel em 2º (mesma espera, aproveita 67%). Abra *Candidatos não elegíveis*
   para mostrar os motivos (duração, profissional, disponibilidade, conflito).
7. **Selecionar** Paula → **Confirmar encaixe**. A agenda mostra o encaixe em ciano e o
   cancelamento preservado.
8. **Importar / Exportar → Exportar agenda** — baixe o CSV final.
9. Para repetir: *Restaurar dados de demonstração*.

## Estrutura

```
app.py          interface Streamlit
database.py     conexão, esquema e transações SQLite
models.py       modelos e validações
scheduler.py    motor de encaixe (puro, testável)
services.py     operações da agenda
csv_handler.py  importação/exportação CSV
seed.py         dados fictícios
styles.css      identidade visual
tests/          pytest (motor, serviços, CSV e smoke test da UI)
```

## Desenvolvimento

- [Arquitetura](docs/ARCHITECTURE.md): camadas, métricas operacionais e limitações de sessão.
- [Guia de contribuição](CONTRIBUTING.md): ambiente local, qualidade e regras para alterações.
