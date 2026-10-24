# Contribuindo com o Agende Bem

## Ambiente local

```powershell
cd web-demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
streamlit run app.py
```

## Antes de enviar uma alteração

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- Não altere `scheduler.py` para mudanças de interface.
- Não inclua credenciais, `.env.local` ou bancos locais em commits.
- Não execute migrations contra produção durante desenvolvimento de UI.
- Prefira componentes nativos do Streamlit, classes CSS próprias `ab-*` e dados derivados de `services.py`.
- Valide desktop, tablet e mobile; navegação por teclado e estados de erro fazem parte do critério de aceite.
