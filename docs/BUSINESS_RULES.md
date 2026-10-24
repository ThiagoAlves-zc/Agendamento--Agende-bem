# Regras de negócio e motor de encaixe

## Importação e lista de espera

O importador aceita CSV UTF-8 separado por `;` ou `,`, com data, horário, duração, profissional e paciente. O limite é um dia, até três profissionais, 500 linhas e 1 MB. Campos iniciados por `=`, `+`, `-` ou `@` são neutralizados na exportação para reduzir CSV Injection.

Cada entrada da lista de espera informa profissionais aceitos, duração, disponibilidade, data de solicitação e situação. Apenas entradas `ativo` podem ser candidatas.

## Janela liberada

Ao cancelar uma consulta, o serviço calcula as janelas livres dentro do expediente do profissional. A consulta cancelada permanece registrada; ela não bloqueia a janela. Janelas inferiores à duração mínima não são sugeridas.

## Elegibilidade

`scheduler.evaluate_candidates` rejeita uma entrada quando qualquer condição falha:

1. solicitação inativa;
2. janela de outro dia;
3. profissional não aceito;
4. duração maior que a janela;
5. disponibilidade do paciente incompatível;
6. sobreposição com consulta do mesmo profissional;
7. sobreposição com consulta do mesmo paciente.

Para candidatos elegíveis, a interface apresenta a justificativa: tempo na lista, profissional compatível, aproveitamento da vaga, disponibilidade e confirmação de ausência de conflito.

## Ordenação

A ordenação é exclusivamente definida em `scheduler.py`: maior número de dias de espera, menor sobra de minutos na janela e menor identificador de cadastro. Não há modelo generativo nem decisão automática.

## Confirmação e consistência

A recepção escolhe o candidato e confirma explicitamente. Em `services.confirm_fit_in`, a janela e a elegibilidade são recalculadas dentro de transação. Se a agenda mudou, a operação é recusada; não há gravação parcial. O banco PostgreSQL também possui restrição de exclusão para impedir consultas confirmadas sobrepostas. A lista de espera e a auditoria são atualizadas junto com o novo atendimento.
