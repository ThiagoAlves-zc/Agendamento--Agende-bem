# Arquitetura do Agende Bem

O Agende Bem é uma aplicação Streamlit com regras de encaixe determinísticas e banco SQLite ou PostgreSQL.

## Camadas

- `app.py`: composição de telas, navegação, estados efêmeros e componentes Streamlit.
- `services.py`: casos de uso, consultas parametrizadas, transações e projeções de leitura.
- `scheduler.py`: motor puro de janelas livres, elegibilidade e ordenação. Não depende da interface ou banco.
- `models.py`: entidades e validações de domínio.
- `database.py`: adaptadores SQLite/PostgreSQL e controle transacional.
- `csv_handler.py`: validação, importação e exportação segura de CSV.
- `seed.py`: cenário sintético de demonstração.

## Princípios

1. A interface não decide a elegibilidade de encaixe.
2. Toda mutação passa por `services.py` e por validação transacional.
3. Métricas operacionais são derivadas de dados persistidos; nunca de valores decorativos.
4. Estados de navegação ficam na URL quando úteis após reconexão; dados críticos ficam no banco.
5. Não registrar dados clínicos, documentos ou credenciais em eventos de auditoria.

## Métricas V2

- **Vagas abertas:** janelas calculadas pelo scheduler dentro do expediente.
- **Tempo recuperado:** duração de atendimentos ativos cuja origem é `encaixe`.
- **Taxa de ocupação:** minutos de consultas ativas divididos pela capacidade de expediente dos profissionais ativos.

## Limitação conhecida

Uma reconexão WebSocket pode reiniciar o estado efêmero do Streamlit em hospedagens serverless. A aplicação preserva operações no banco e revalida encaixes, mas a estabilidade completa exige uma plataforma com sessão persistente/processo de longa duração.
