# Roadmap e limitações

## Limitações atuais

- Streamlit em Vercel serverless pode perder estado efêmero em reconexões WebSocket.
- A solução é destinada a uma clínica, um dia e até três profissionais.
- Lista de espera e profissionais possuem modelos de referência; nem todos possuem importação automática.
- A entidade de pacientes está preparada, mas vínculos legados por nome não foram migrados automaticamente.
- A aplicação não deve receber dados clínicos ou documentos pessoais sem subfase própria de privacidade, autenticação e autorização.

## Próximos passos

1. Hospedagem com processo persistente e afinidade de sessão para operação contínua.
2. Gestão controlada de pacientes com resolução de duplicidade antes de vincular registros existentes.
3. Edição/remarcação somente reutilizando validação de disponibilidade e confirmação.
4. Versionamento de modelos com interface administrativa completa.
5. Relatórios operacionais exportáveis e observabilidade de infraestrutura.

Nenhum item de roadmap deve ser interpretado como funcionalidade entregue.
