# V3.2 — homologação integrada Supabase local

## Resultado da inspeção (2026-10-24)

| Item | Resultado |
|---|---|
| Docker Desktop / daemon | Indisponível (`docker` não está no `PATH`) |
| Podman / nerdctl | Indisponíveis |
| WSL | Comando presente, mas não é runtime de containers por si só |
| Supabase CLI | `2.78.1` (`2.122.0` disponível, não atualizado) |
| Projeto Supabase hospedado | Não consultado, vinculado ou modificado |

`supabase start --help` confirma que a CLI inicia uma pilha de containers.
Sem um runtime compatível não é possível iniciar localmente Postgres, GoTrue,
Storage API, Kong e Mailpit como uma integração Supabase real. Não foi
instalado nenhum software, criada conta ou projeto pago.

## Bloqueio objetivo

O Gate V3.2 não pode alegar homologação end-to-end de Auth e Storage no estado
atual. PostgreSQL 17 descartável continua adequado para as migrations e regras
transacionais, mas não emula as APIs Auth, Storage e políticas do Supabase.
Mocks de Storage também não substituem esse teste.

## Procedimento autorizado quando houver Docker Desktop

Execute somente em uma cópia/checkout local isolado, sem `supabase link` e sem
credenciais hospedadas:

```powershell
supabase init
supabase start
supabase status -o env
```

Antes de iniciar, reserve e registre as portas exibidas por `supabase status`.
Não presumir valores: a CLI pode escolhê-los ou eles podem conflitar com o
Streamlit e clusters PostgreSQL descartáveis. Parar a pilha ao final:

```powershell
supabase stop
```

Depois de revisar o `config.toml` local, aplicar as migrations do projeto na
ordem `0001` a `0005` exclusivamente na base local. A convenção atual do
Agende Bem mantém essas migrations em `web-demo/migrations/postgres`; não se
deve usar `db push` contra projeto remoto.

## Plano de evidências obrigatório

1. Criar usuários fictícios no GoTrue local e registrar seus IDs em
   `agende_bem.app_users` por bootstrap administrativo controlado.
2. Exercitar login, refresh, logout, revogação, conta sem papel e os três
   papéis operacionais. Após reconectar Streamlit, exigir uma nova sessão se
   `st.session_state` tiver sido perdido; jamais restaurar um papel sem validar
   `GET /auth/v1/user` e `app_users` novamente.
3. Criar o bucket privado `agende-bem-operacional` somente na pilha local e
   aplicar políticas que neguem acesso público. Validar CSV/PDF, 5 MB, SHA-256,
   falha compensada, arquivamento e catálogo idempotente.
4. Executar testes PostgreSQL com uma URL marcada explicitamente como
   descartável e registrar os resultados separadamente de Auth/Storage.
5. Executar Streamlit com somente as variáveis retornadas por `supabase status`
   para a pilha local; capturar desktop, tablet e mobile após cada fluxo.

## Risco de sessão Streamlit

`st.session_state` pertence à sessão WebSocket. Em desconexão, não deve ser
tratada como armazenamento persistente de identidade. A implementação V3.1-B
limpa ator/sessão quando a validação Auth falha; uma homologação local precisa
provar que uma sessão nova não herda tokens ou o `Actor` anterior. Para uma
experiência com reconexão transparente será necessário um mecanismo de sessão
servidor com rotação/revogação, avaliado separadamente; não é seguro copiar
refresh tokens para URL ou HTML.
