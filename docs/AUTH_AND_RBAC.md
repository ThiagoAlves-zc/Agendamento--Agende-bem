# Autenticação e RBAC

## Fluxo de identidade

1. Supabase Auth valida e-mail/senha.
2. A aplicação consulta o usuário autenticado a cada execução relevante.
3. `identity_service.actor_for_verified_user` procura o `user_id` em `agende_bem.app_users`.
4. `authorization.require` valida a permissão antes da operação de servidor.

O JWT não escolhe o papel por metadado editável. Cadastro público deve permanecer desabilitado em operação; o primeiro administrador é criado pelo procedimento administrativo documentado, nunca por parâmetro de URL.

## Matriz efetiva

| Permissão | Administrador | Recepção | Leitura |
| --- | :---: | :---: | :---: |
| Ver agenda e histórico | Sim | Sim | Sim |
| Cancelar e confirmar encaixe | Sim | Sim | Não |
| Gerenciar lista de espera | Sim | Sim | Não |
| Baixar arquivos | Sim | Sim | Sim |
| Enviar/arquivar arquivos | Sim | Não | Não |
| Gerenciar modelos, configurações e usuários | Sim | Não | Não |

## Limite de isolamento

O Streamlit usa uma role compartilhada de banco. Por isso, a autorização da aplicação é obrigatória antes de cada operação; Supabase Auth isoladamente não protege operações realizadas por essa conexão server-side. A tabela privada, grants mínimos e RLS reduzem exposição, mas não substituem autenticação real no limite da aplicação.
