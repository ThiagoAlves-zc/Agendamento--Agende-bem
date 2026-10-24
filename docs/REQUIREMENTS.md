# Requisitos

## Funcionais do desafio

1. Importar agenda de um único dia por CSV.
2. Limitar a agenda a três profissionais.
3. Cadastrar entradas de lista de espera com duração, disponibilidade e profissionais aceitos.
4. Cancelar atendimento após confirmação.
5. Exibir janelas livres e candidatos elegíveis/inelegíveis.
6. Confirmar manualmente um encaixe e salvar a agenda atualizada.
7. Exportar a agenda atualizada em CSV.

## Funcionais da evolução V3

- Dashboard, timeline, histórico e indicadores derivados de dados persistidos.
- Autenticação por e-mail/senha e papéis Administrador, Recepção e Leitura.
- Biblioteca operacional privada de CSV/PDF e modelos reutilizáveis.
- Auditoria de operações e prevenção de cliques duplicados pelo fluxo transacional.

## Não funcionais

- Regras do motor separadas da interface e cobertas por testes.
- SQLite local e PostgreSQL compatíveis.
- Sem dados clínicos, CPF ou documentos pessoais no escopo atual.
- Validação de entrada, transações e proteção contra sobreposição.
- Layout responsivo priorizando operação em desktop.
- Indicadores calculados a partir do banco, sem valores decorativos.
