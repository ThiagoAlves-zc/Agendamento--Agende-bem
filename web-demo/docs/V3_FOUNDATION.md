# Fundação V3: pacientes e biblioteca operacional

## Estado desta etapa

Esta etapa prepara o schema e a validação de arquivos sem criar recursos no
Supabase, sem carregar dados e sem expor uma biblioteca visual que não possa
funcionar de ponta a ponta. A migration `0004_v3_foundation.sql` ainda **não foi
aplicada** ao projeto pessoal.

## Dados e migração de pacientes

`patients` introduz um identificador interno único, nome de exibição e estado
ativo/inativo. Consultas e lista de espera existentes continuam usando nomes.
Isso é deliberado: não há garantia segura de que dois nomes iguais no histórico
representem a mesma pessoa. Uma migration futura só poderá adicionar FKs depois
de uma revisão/manual de ambiguidades e de autenticação operacional.

## Biblioteca de arquivos

O PostgreSQL privado registra somente metadados em `file_assets`:

- nome original e nome de exibição;
- extensão/MIME permitido, tamanho e SHA-256;
- bucket/chave do Storage, categoria e estado;
- datas de criação e atualização.

`file_templates` e `file_template_versions` mantêm a versão atual e o histórico
de modelos. O conteúdo continua fora do banco, em Storage privado.

## Contrato de Storage para a próxima etapa

1. Provisionar um bucket privado, por exemplo `agende-bem-operacional`, usando
   API ou Dashboard do Supabase — nunca `INSERT`/`DELETE` direto no schema
   `storage`.
2. Configurar máximo de 5 MB por arquivo e MIME `text/csv` e `application/pdf`.
3. Implementar Supabase Auth e perfis antes de criar políticas por usuário.
4. Executar upload/download somente no servidor, com credencial protegida em
   variável de ambiente. Nunca enviar uma service key ao navegador.
5. Gerar chaves imutáveis e URLs assinadas curtas para download. Nunca usar
   sobrescrita de objetos para criar versões.

Até existir autenticação própria, a biblioteca deve aceitar somente modelos e
arquivos operacionais sem dados pessoais. Documentos de pacientes continuam fora
do escopo.

## Validação local

`file_validation.py` aceita apenas CSV UTF-8 e PDF com assinatura `%PDF-`, até
5 MB. Ele rejeita caminho, traversal, caracteres de controle, extensão/MIME
incompatível e conteúdo inválido. A camada de Storage deve reutilizá-lo antes de
qualquer envio.

## Custos e limites a confirmar antes de provisionar

O Supabase Free permite limite global de arquivo de até 50 MB; esta aplicação
limita cada arquivo a 5 MB. Os limites de capacidade, egress e retenção variam
por plano e devem ser conferidos no dashboard da conta antes de ativar uploads.
Como o projeto está protegido pela Vercel, mas ainda não tem RBAC interno, não
há autorização suficiente para ativar arquivos reais.
