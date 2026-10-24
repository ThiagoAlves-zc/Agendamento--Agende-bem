# Auditoria V3 — Agende Bem

Data da auditoria: 24/10/2026. Base: `12adf74` (V2.1).

## Inventário técnico

| Área | Estado atual | Reaproveitamento V3 |
|---|---|---|
| Interface | Streamlit em `app.py`, CSS próprio `ab-*` | cabeçalho, sidebar, diálogos, timeline e feedbacks |
| Domínio | `models.py`, `services.py`, `scheduler.py` | regras e transações; o scheduler não deve ser alterado por UI |
| Dados | SQLite local e PostgreSQL privado `agende_bem` | adaptadores, pool, migrations e testes em dois bancos |
| Importação | CSV validado com proteção contra fórmula | modelo de agenda e fluxo de importação |
| Demonstração | `seed.py` com dados sintéticos | roteiro repetível, exclusivamente em modo demo |
| Infraestrutura | Streamlit em container Vercel + Supabase | Preview protegido; não apropriado para sessão persistente contínua |

## Dados atuais e separação de ambientes

O cenário visto no Preview contém somente os nomes e consultas sintéticos de
`seed.py`. A auditoria não consultou nem alterou o banco pessoal remoto. Não foi
executada limpeza, backup, `DELETE`, `TRUNCATE` ou reset fora do cluster local
descartável de testes.

Hoje, o aplicativo inicializa o cenário de demonstração quando o banco está
vazio. A subfase operacional deve introduzir configuração explícita de ambiente
antes de aceitar qualquer dado real, com estados vazios e sem restauração
automática. A migração de nomes de pacientes existentes para identificadores é
intencionalmente adiada: um nome não é uma identidade confiável.

## Auditoria visual

- O Figma fornece oito quadros de referência: Dashboard, Agenda, Lista de
  Espera, Sugestões, CSV, cancelamento, confirmação e sucesso.
- Em 1440 px, o Preview apresenta hierarquia clara, sidebar estável e não houve
  overflow horizontal nas rotas que responderam.
- Em 768 px, a timeline proporcional comporta três profissionais sem overflow
  do documento.
- Em 390 px, o seletor de profissional permite limitar a timeline a uma coluna.
  Com “Todos os profissionais” selecionado, a rolagem é interna à timeline; a
  próxima iteração deve tornar a escolha de um profissional mais evidente.

## Resiliência observada

Durante a navegação de homologação, uma abertura do Dashboard retornou
`500 INTERNAL_FUNCTION_INVOCATION_FAILED`. Um reload recuperou a tela e não
houve erro no console. Isso é compatível com a limitação já documentada de
Streamlit em Functions da Vercel, não uma correção comprovada de WebSocket.

## Relatório de segurança

### Achados críticos

Nenhum segredo foi encontrado nos arquivos versionados revisados. Nenhuma
credencial, chave de serviço ou URL administrativa foi adicionada nesta etapa.

### Riscos que bloqueiam a biblioteca com arquivos reais

1. **Alto — ausência de autenticação e RBAC internos.** Vercel Authentication
   protege o deployment, mas não identifica papéis de recepção/administração na
   aplicação. Ativar upload de documentos reais agora geraria acesso sem
   autorização granular.
2. **Alto — reset de demonstração não é compatível com dados operacionais.** A
   função atual de reset é corretamente restrita ao papel da aplicação, porém
   esvazia as tabelas da demonstração. Ela não pode coexistir com dados reais
   sem modo operacional separado e autorização administrativa.
3. **Médio — Storage ainda não foi provisionado.** Não criar políticas permissivas
   em `storage.objects`; buckets privados e URLs assinadas devem ser ativados só
   junto com Supabase Auth/RBAC.
4. **Médio — Streamlit serverless perde estado efêmero em reconexões.** As
   transações protegem gravações, mas formulários/seleções em andamento podem
   exigir repetição após reciclagem de instância.

### Controles implementados nesta fundação

- schema privado `agende_bem`, sem exposição à Data API;
- RLS e privilégios apenas para `agende_bem_app` nas novas tabelas;
- sem manipulação direta do schema `storage`;
- validação local de nomes, extensão, MIME, assinatura PDF, UTF-8 CSV, tamanho
  máximo de 5 MB e SHA-256;
- testes PostgreSQL confirmam que `anon`/`authenticated` não leem as novas
  tabelas e que a unicidade de paciente é case-insensitive.

## Próximas subfases recomendadas

1. Aprovar e aplicar a migration `0004` apenas em ambiente de homologação
   dedicado; validar backup e advisors antes do Supabase pessoal.
2. Implementar Supabase Auth, perfis e autorização no servidor.
3. Provisionar bucket privado via API/Dashboard, com limite de 5 MB e MIME CSV/PDF.
4. Implementar serviço de Storage e UI de Arquivos/Modelos somente após os itens
   anteriores; os modelos devem ser criados sem dados pessoais.
5. Introduzir modo operacional explícito, estados vazios e plano de reconciliação
   de identidades antes de vincular consultas/lista de espera a `patients`.
