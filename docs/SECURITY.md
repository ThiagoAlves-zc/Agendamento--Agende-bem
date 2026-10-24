# Segurança e privacidade

## Princípios

O escopo usa somente dados sintéticos e arquivos operacionais sem dados pessoais. Não deve ser tratado como sistema clínico pronto para dados reais nem como declaração de conformidade legal.

## Autenticação e sessão

Supabase Auth valida e-mail/senha. Tokens permanecem no processo Streamlit, em `st.session_state`; não são inseridos na URL, HTML ou logs. Em cada rerun, `current_user` confirma a identidade e a aplicação renova sessões próximas da expiração. Logout chama o endpoint Auth e remove o estado local.

Uma desconexão WebSocket pode encerrar a sessão efêmera. Uma nova sessão não herda identidade ou papel: precisa passar novamente pela validação Auth e por `app_users`.

## RBAC

| Papel | Permitido |
| --- | --- |
| Administrador | Todas as operações, usuários, arquivos e modelos |
| Recepção | Agenda, lista de espera, cancelamento, encaixe, histórico e download |
| Leitura | Consulta de agenda/histórico/arquivos e download |

Esconder botões é apenas conveniência de UX. As operações chamam `require()` no servidor. O papel não vem de `user_metadata` editável pelo usuário; vem da tabela privada `agende_bem.app_users` após Auth verificar a identidade.

## Arquivos

O bucket é privado. A aplicação gera chaves de objeto não previsíveis, aceita somente CSV/PDF operacional de até 5 MB, verifica MIME, nome, assinatura PDF/UTF-8 CSV e SHA-256. Metadados ficam em PostgreSQL. Se a gravação de metadados falhar após upload, o serviço tenta remover o objeto para reduzir órfãos.

## Banco e privacidade

Consultas são parametrizadas. O papel `agende_bem_app` tem privilégios mínimos e o schema privado não é exposto pela Data API. Eventos de auditoria não devem receber segredos, conteúdo de arquivo, prontuário, CPF ou diagnóstico.

## Operação segura

- Use segredos apenas em variáveis server-side, cofre local ou painel do provedor.
- Não versione `.env`, bancos SQLite, tokens ou connection strings.
- Não execute reset, `TRUNCATE`, `DROP` ou fixtures PostgreSQL contra o Supabase hospedado.
- Revise RLS, grants e bucket antes de qualquer uso de documentos reais.

## Pendência de publicação

Uma credencial administrativa foi informada anteriormente fora do repositório. A rotação dessa credencial deve ser confirmada pelo titular no painel do provedor antes de considerar a revisão de segurança encerrada. Esta documentação não registra nem reproduz o valor da credencial.
