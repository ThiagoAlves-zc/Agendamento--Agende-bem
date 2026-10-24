# Visão geral do projeto

## Contexto

O Agende Bem foi desenvolvido para o OpenAI Hackathon, Saúde — Desafio 2: agenda inteligente para uma clínica. O objetivo é apoiar a recepção quando um cancelamento abre uma vaga na agenda.

## Escopo original

- carregar agenda CSV;
- cadastrar lista de espera;
- sugerir encaixes por horário, duração e profissional;
- confirmar substituição;
- salvar e exportar agenda atualizada;
- operar para uma clínica, um dia e até três profissionais.

## Proposta implementada

O sistema transforma a vaga liberada em candidatos explicáveis e ordenados. Ele mantém a decisão humana e protege a confirmação com revalidação transacional. Dashboard, Auth/RBAC, arquivos, modelos e histórico são evoluções adicionais da V3.

## Fora do escopo

Não há diagnóstico, recomendação médica, prontuário, CPF, tratamento de dados reais de pacientes ou IA generativa no motor de sugestões.

Consulte [REQUIREMENTS.md](REQUIREMENTS.md), [BUSINESS_RULES.md](BUSINESS_RULES.md) e [hackathon/CHALLENGE_02.md](hackathon/CHALLENGE_02.md).
