# Guia de uso

## Perfis

| Perfil | Rotina principal |
| --- | --- |
| Administrador | Gerencia usuários, modelos, arquivos e acompanha toda a operação |
| Recepção | Consulta agenda, cadastra espera, cancela e confirma encaixes |
| Leitura | Consulta agenda, histórico e baixa arquivos permitidos |

## Fluxo da recepção

1. Abra **Agenda** e selecione data/profissional ou a timeline.
2. Escolha um atendimento e confirme o cancelamento.
3. Abra **Central de encaixes** para a janela liberada.
4. Compare justificativas de candidatos elegíveis e motivos dos inelegíveis.
5. Selecione um candidato e confirme. A aplicação revalida antes de salvar.
6. Confira a Agenda atualizada e exporte CSV, se necessário.

## Lista de espera

Use pesquisa, filtros e ordenação para localizar entradas. No cadastro, informe duração, janela de disponibilidade e profissionais aceitos. A entrada não garante atendimento; ela será avaliada para cada vaga real.

## Arquivos e modelos

Administradores enviam CSV/PDF operacional de até 5 MB. Todos os perfis autorizados podem consultar e baixar itens ativos; somente administrador arquiva ou registra modelos. Modelos de lista de espera e profissionais são referências quando não houver importação correspondente.

## Recuperação e erros

Após reconexão WebSocket, confirme se a página e o estado do formulário foram preservados. Dados já gravados devem ser conferidos na Agenda ou Histórico antes de repetir uma ação. Mensagens de erro não devem conter segredos ou detalhes de conexão.
