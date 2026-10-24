# Aplicação Agende Bem

Esta pasta contém a aplicação Streamlit do Agende Bem. O contexto do Hackathon, arquitetura, regras de negócio, segurança e material de apresentação estão no [README da raiz](../README.md) e em [`../docs/`](../docs/README.md).

## Desenvolvimento local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
streamlit run app.py
```

Por padrão, a aplicação usa SQLite em `data/agende_bem.db` e dados sintéticos. As migrations SQLite são aplicadas automaticamente. Para PostgreSQL/Supabase, copie `.env.example` para um arquivo local ignorado e configure somente valores fora do Git.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes PostgreSQL que criam bancos exigem `TEST_PG_ADMIN_URL` apontando para uma instância descartável. Nunca use o Supabase hospedado para essas fixtures.

## Módulos principais

| Módulo | Responsabilidade |
| --- | --- |
| `app.py` | Interface, navegação, autenticação e diálogos |
| `scheduler.py` | Elegibilidade e ordenação determinística de encaixes |
| `services.py` | Casos de uso, transações e auditoria |
| `database.py` | Adaptadores SQLite/PostgreSQL e migrations |
| `csv_handler.py` | Importação/exportação protegida de CSV |
| `file_library.py` | Metadados PostgreSQL e Storage privado |
| `authorization.py` | Matriz RBAC no servidor |

Consulte [DEPLOY.md](DEPLOY.md) para o histórico operacional e [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) para o guia consolidado.
