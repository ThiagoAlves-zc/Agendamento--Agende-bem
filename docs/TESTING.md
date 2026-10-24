# Testes e validações

## Execução local

```powershell
cd web-demo
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado registrado na V3.3: **63 passed, 40 skipped** em 64,69 s. Os 103 testes coletados incluem SQLite, regra de negócio, CSV, autenticação, autorização, biblioteca, runtime Streamlit e variantes PostgreSQL.

## PostgreSQL isolado

```powershell
# Defina TEST_PG_ADMIN_URL por cofre local ou variável de sessão para um PostgreSQL descartável.
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_PG_ADMIN_URL
```

Essa fixture cria e remove `agende_bem_test`, aplica migrations e valida concorrência, RLS, privilégios, rollback e restrição de sobreposição. Portanto, ela só pode apontar para um cluster descartável e autorizado. Sem `TEST_PG_ADMIN_URL`, as variantes PostgreSQL são ignoradas deliberadamente.

## Smoke remoto não destrutivo

`scripts/check_deploy.py` valida que a proteção externa bloqueia acessos não autenticados. O smoke V3 integrado validou login/refresh/logout, RBAC, download com hash, upload e arquivamento usando apenas conta e arquivo sintéticos identificáveis.

## Evidências pendentes

Capturas visuais em 1440, 768 e 390 px devem ser feitas com navegador pessoal autorizado, usando somente dados sintéticos. Não registre testes ignorados como aprovados.
