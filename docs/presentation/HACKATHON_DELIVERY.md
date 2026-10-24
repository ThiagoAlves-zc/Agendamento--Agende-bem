# Entrega — OpenAI Hackathon

## Problema

Cancelamentos deixam janelas vazias e exigem que a recepção compare rapidamente lista de espera, profissional, duração e disponibilidade.

## Solução

Agende Bem importa a agenda, registra espera, identifica vagas e apresenta candidatos compatíveis com justificativas. A recepção confirma manualmente; a operação é revalidada antes da gravação.

## Diferenciais

- Ordenação determinística, explicável e testável.
- Bloqueio de sobreposição no serviço e no PostgreSQL.
- Interface de agenda, timeline, histórico e exportação.
- Evolução V3 com autenticação, RBAC e biblioteca privada de modelos.

## Demonstração

Siga [DEMO_SCRIPT.md](../DEMO_SCRIPT.md): Agenda → cancelamento → candidatos → confirmação → agenda atualizada → exportação.

## Stack e limites

Python, Streamlit, SQLite/PostgreSQL, Supabase e Vercel. O MVP é limitado a uma clínica, um dia e três profissionais; o motor é determinístico, não IA generativa. A estabilidade de WebSocket em serverless é uma limitação conhecida.

## Resultados comprovados

Testes locais V3.3: 63 aprovados, 40 ignorados por exigirem PostgreSQL descartável. O fluxo de Auth/RBAC/Storage foi validado com contas e arquivos sintéticos no ambiente autorizado.
