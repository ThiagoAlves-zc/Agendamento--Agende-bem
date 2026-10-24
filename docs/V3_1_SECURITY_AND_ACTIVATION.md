# V3.1-B — segurança e ativação controlada

## Limite de segurança

O Streamlit conecta ao PostgreSQL como `agende_bem_app`, uma role técnica
compartilhada. Ela não representa o usuário final. Por isso, cada mutação
exposta pela V3.1-B deve atravessar esta sequência no processo do servidor:

```
Supabase Auth (sessão/JWT) -> GET /auth/v1/user -> app_users privado
-> Actor(role) -> require(permission) -> serviço transacional -> PostgreSQL/Storage
```

O JWT serve somente para confirmar `user_id` e e-mail. O papel nunca é lido de
`user_metadata`, parâmetros de URL, widgets ou estado enviado pelo browser.
`app_users` é a fonte de autorização e precisa conter o mesmo `user_id` e e-mail
validado pelo Auth. Isto impede que uma sessão altere o próprio papel no cliente.

Enquanto essa role técnica existir, RLS por si só não fornece isolamento por
usuário dentro do Streamlit: a verificação no serviço é obrigatória e não pode
ser substituída por esconder botões. Uma futura arquitetura com JWT propagado ao
PostgREST poderá acrescentar RLS por identidade, mas não substitui essa camada.

## Matriz RBAC

| Operação | Administrador | Recepção | Leitura |
|---|---:|---:|---:|
| Consultar agenda, histórico e arquivos | sim | sim | sim |
| Cancelar, lista de espera e encaixar | sim | sim | não |
| Download de arquivos ativos | sim | sim | sim |
| Upload, arquivar e gerir modelos | sim | não | não |
| Gerir usuários e configurações | sim | não | não |

As permissões são enumeradas em `web-demo/authorization.py`; os serviços de
arquivo chamam `require()` antes de cada operação. As ações existentes de
cancelamento e confirmação de encaixe também verificam a permissão no callback
do servidor. A confirmação transacional de encaixe permanece no serviço atual.

## Primeiro administrador (procedimento seguro)

Não habilite cadastro público. Primeiro crie e confirme o usuário no painel
Supabase Auth. Em seguida, um operador com acesso local ao servidor executa uma
única vez `bootstrap_first_admin()` com o `user_id` e e-mail retornados por
`GET /auth/v1/user` e com `AGENDE_BEM_BOOTSTRAP_TOKEN` definido apenas no
ambiente protegido. O método usa comparação de tempo constante, só funciona se
`app_users` estiver vazio e não existe rota, URL ou formulário público para ele.

Após o bootstrap, remova o token do ambiente. Administradores usam a tela
**Usuários e permissões** para alterar outros papéis; não podem remover o próprio
papel de administrador pela interface.

## Arquivos e modelos

- Bucket planejado: `agende-bem-operacional`, privado.
- Conteúdo: somente CSV e PDF operacionais, limite da aplicação de 5 MB.
- Objetos: chaves UUID não previsíveis sob `operacional/` ou `modelo/`.
- Metadados: `agende_bem.file_assets`; SHA-256 é verificado no download.
- Storage é acessado apenas pela API de Storage no servidor com
  `SUPABASE_SECRET_KEY`; a chave não é enviada ao browser.
- O upload envia o objeto antes de gravar metadados; se a transação do banco
  falhar, tenta apagar o objeto como compensação. Falha na compensação deve ser
  reconciliada pelo operador, sem mascarar o erro original.
- Arquivar preserva o objeto e torna os metadados indisponíveis para download.
- O catálogo de cinco modelos é idempotente e só é registrado por administrador
  após o bucket privado existir. Modelos de lista de espera e profissionais são
  explicitamente arquivos de referência: não prometem importação automática.

## Ordem de ativação (não executada nesta entrega)

1. Criar um projeto Supabase de homologação separado e confirmar custos/cotas.
2. Aplicar `0001` a `0005` nessa ordem com operador de migration.
3. Criar o bucket privado `agende-bem-operacional`; não manipular tabelas do
   schema `storage` diretamente.
4. Criar políticas de Storage que neguem acesso público e somente permitam a
   integração de servidor autorizada. Revisar as políticas com o Security
   Advisor antes de gravar qualquer arquivo.
5. Configurar no servidor `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
   `SUPABASE_SECRET_KEY`, `AGENDE_BEM_AUTH_REQUIRED=true` e URL de redirect de
   recuperação previamente permitida no Auth. Nunca usar chaves legadas no
   navegador ou logs.
6. Criar um usuário fictício, executar o bootstrap do primeiro administrador,
   validar os perfis recepção e leitura e registrar o catálogo de modelos.
7. Só então avaliar produção com backup verificável e revisão independente.

Nenhuma migration, bucket, conta, política ou variável do projeto de produção
`fvrjxoycosmuujxvhnpm` foi alterada por esta entrega.

## Limitações e bloqueios

- Não há ambiente Supabase de homologação autorizado, portanto Auth e Storage
  reais não foram validados remotamente; os testes usam `MemoryStorage` local.
- Não foi feito deploy, push, merge ou alteração do Preview/produção.
- A proteção da Vercel continua sendo uma barreira externa, não RBAC interno.
- A desconexão WebSocket da hospedagem permanece uma limitação de infraestrutura;
  perda de sessão exige novo login e as mutações críticas continuam revalidadas
  pelo serviço.
