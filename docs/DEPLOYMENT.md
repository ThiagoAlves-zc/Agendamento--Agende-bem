# Deployment

## Ambientes

| Ambiente | Banco | Agente de dados | Finalidade |
| --- | --- | --- | --- |
| Local | SQLite | dados sintéticos | desenvolvimento e demonstração |
| Preview | PostgreSQL/Supabase autorizado | configuração de Preview | homologação protegida |
| Produção | PostgreSQL/Supabase autorizado | configuração de Produção | demonstração publicada |

O deployment atual é protegido pela Vercel Authentication. Não use esse controle como substituto de RBAC interno.

## Variáveis server-side

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | conexão TLS da role de aplicação |
| `STREAMLIT_SERVER_COOKIE_SECRET` | segredo do cookie Streamlit |
| `SUPABASE_URL` | endpoint do projeto Supabase |
| `SUPABASE_PUBLISHABLE_KEY` | chave usada pelo cliente Auth no servidor |
| `SUPABASE_SECRET_KEY` | somente Storage/Admin server-side |
| `AGENDE_BEM_AUTH_REQUIRED` | exige login operacional |
| `AGENDE_BEM_DEMO_MODE` | controla seed de demonstração |
| `AGENDE_BEM_AUTH_REDIRECT_URL` | redirecionamento de recuperação |

Nunca copie valores reais para exemplos, commits ou screenshots.

## Processo seguro

1. Rode `python migrate.py --dry-run` com conexão administrativa local e Project Ref conferido.
2. Aplique somente migrations aditivas revisadas.
3. Configure secrets no escopo correto da Vercel.
4. Faça Preview protegido e execute smoke tests não destrutivos.
5. Promova somente após validação de Auth, RBAC, Storage e fluxo de encaixe.

O Docker local não é requisito para o projeto: a Vercel constrói o container remotamente. O documento histórico [`web-demo/DEPLOY.md`](../web-demo/DEPLOY.md) registra detalhes da implantação e limitações conhecidas.
