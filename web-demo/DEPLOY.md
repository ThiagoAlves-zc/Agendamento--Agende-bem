# Deploy privado — Vercel + Supabase

Status: **preparado, não implantado.** Nada foi enviado à Vercel nem ao Supabase.
Pré-requisitos ainda pendentes estão em [Pendências](#pendências).

## Arquitetura

```
Navegador ──HTTPS/WSS──▶ Vercel (Deployment Protection: Vercel Authentication, All Deployments)
                           └─ container Dockerfile.vercel (Streamlit, região gru1)
                                 └─ pool psycopg (≤3 conexões/instância, TLS)
                                       └─ Supabase Supavisor (modo transação, 6543)
                                             └─ PostgreSQL: esquema privado agende_bem
```

- Local: sem `DATABASE_URL`, a aplicação continua usando SQLite (`data/agende_bem.db`).
- Remoto: `DATABASE_URL` aponta para o papel `agende_bem_app` (privilégio mínimo).

## 1. Supabase (projeto NOVO e dedicado)

> Não reutilize os projetos do CRM ou do TrilhaX. `migrate.py` recusa aplicar migrations
> se o `--project-ref` informado não estiver na URL.

1. Crie um projeto novo na região **South America (São Paulo) — sa-east-1**.
2. Em *Project Settings → Data API*, **não** adicione `agende_bem` aos *Exposed schemas*.
3. Na sua máquina, com a credencial administrativa apenas na sessão do terminal:

   ```powershell
   cd web-demo
   $env:DATABASE_ADMIN_URL = "<connection string do Session pooler (5432), usuário postgres>"
   .venv\Scripts\python migrate.py --project-ref <REF> --dry-run
   .venv\Scripts\python migrate.py --project-ref <REF>
   Remove-Item Env:DATABASE_ADMIN_URL
   ```

4. No *SQL Editor* do Supabase, habilite o login do papel da aplicação com uma senha forte
   gerada fora do Git (ex.: `python -c "import secrets; print(secrets.token_urlsafe(32))"`):

   ```sql
   ALTER ROLE agende_bem_app WITH LOGIN PASSWORD '<senha forte>';
   ```

5. Monte a `DATABASE_URL` com o **Transaction pooler** (porta 6543), usuário com sufixo do projeto:

   ```
   postgresql://agende_bem_app.<REF>:<senha>@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```

   O host exato aparece em *Connect → Transaction pooler*. `sslmode` abaixo de `require`
   é recusado pela aplicação. Para `verify-full`, baixe o certificado CA do Supabase e
   acrescente `&sslrootcert=<caminho>` (exige incluir o arquivo na imagem).

### Migrations

| Versão | Conteúdo |
|---|---|
| `0001_schema` | Esquema `agende_bem`, `btree_gist` (em `extensions` no Supabase), 5 tabelas, índices, `CHECK`s e restrição de exclusão que impede consultas confirmadas sobrepostas |
| `0002_app_role` | Papel `agende_bem_app` (NOLOGIN até o passo 4), `search_path`, timeouts, DML nas 5 tabelas, `REVOKE` para `PUBLIC`/`anon`/`authenticated`, RLS com política só para o papel da aplicação |
| `0003_reset_function` | `agende_bem.reset_demo_data()` (`SECURITY DEFINER`) para o reset dos dados fictícios sem conceder `TRUNCATE` ao papel |

`migrations/sqlite/0001_initial.sql` mantém o SQLite local; a aplicação aplica migrations
SQLite automaticamente. No PostgreSQL ela só **verifica** a versão (não executa DDL).

## 2. Vercel

1. Crie o projeto importando o repositório **privado** (ver pendências) e defina
   *Root Directory* = `web-demo`. A Vercel detecta `Dockerfile.vercel`.
2. *Settings → Deployment Protection*: **Vercel Authentication** com escopo
   **All Deployments** (disponível em todos os planos; protege previews e produção).
3. Opcional, para o verificador automatizado: *Protection Bypass for Automation* → gere
   um segredo e guarde fora do Git.
4. *Settings → Environment Variables* (Production e Preview, tipo **Sensitive**):

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | URL do passo 1.5 |
   | `STREAMLIT_SERVER_COOKIE_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `DB_POOL_MAX_SIZE` | `3` (opcional) |

5. *Settings → Functions*: região **São Paulo (gru1)** (também em `vercel.json`) e
   *Max Duration* no máximo permitido pelo plano (300 s Hobby; até 800 s Pro).
6. Faça o deploy e rode o verificador:

   ```powershell
   .venv\Scripts\python scripts\check_deploy.py https://<deploy>.vercel.app
   $env:VERCEL_AUTOMATION_BYPASS_SECRET = "<segredo>"
   .venv\Scripts\python scripts\check_deploy.py https://<deploy>.vercel.app
   ```

7. Teste manual no navegador autenticado: cancelar → sugestões → confirmar encaixe →
   importar CSV (arquivo e "colar conteúdo") → exportar (botão e link alternativo) →
   aguardar > Max Duration e confirmar reconexão automática na mesma página.

## Compatibilidade Streamlit × Vercel

| Ponto | Evidência | Impacto | Mitigação nesta branch |
|---|---|---|---|
| WebSocket | Beta pública em Functions/containers; conexão presa a uma instância | Funciona, mas não é GA | Testar no deploy (`check_deploy.py`) |
| Duração máxima | Containers: 300 s padrão, 800 s Pro; beta de 1800 s não cobre containers | WebSocket cai a cada 5–13 min e o navegador reconecta | Página atual na URL (`?pagina=`); dados no Postgres; teste de reinício |
| Instâncias sem afinidade | "each request can land on a different instance" | Reconexão pode criar sessão nova (perde seleção em andamento, não dados) | Nenhum estado de negócio em memória |
| Upload/download do Streamlit | `MemoryUploadedFileManager` e `MemoryMediaFileStorage` (memória da instância) | Com 2+ instâncias, upload ou download pode falhar | "Colar conteúdo do CSV" e "Link alternativo de download" trafegam só pelo WebSocket |
| Escala a zero | Sem tráfego por 5 min (produção) a instância é desligada | Cold start na primeira visita | Pool com `min_size=0` e `check_connection` |
| Secure Compute / IP fixo | Não suportados em containers | Sem allowlist de IP no Supabase | TLS obrigatório + papel de privilégio mínimo |

**Avaliação:** compatível para uma demonstração interna de baixo tráfego, com as limitações
acima. Se o teste no deploy mostrar quedas frequentes ou falhas de upload/download, a
alternativa recomendada **sem reescrever a interface** é publicar o mesmo container em um
serviço com processo persistente e afinidade de sessão na região de São Paulo, por exemplo
Google Cloud Run (`southamerica-east1`, com *session affinity* e IAP) ou Fly.io (`gru`),
mantendo o Supabase.

## Pendências

1. **Repositório privado**: `ThiagoAlves-zc/Agendamento--Agende-bem` é **público**. Criar
   um repositório privado (ou tornar este privado) antes de enviar esta branch.
2. **Projeto Supabase novo**: informar o *project ref* e a região para aplicar as migrations.
3. **Acesso à Vercel**: time/plano e confirmação de Vercel Authentication em All Deployments.
4. **Build da imagem**: Docker não está instalado nesta máquina; o `Dockerfile.vercel` não
   foi construído localmente (o primeiro build ocorrerá na Vercel).
