# Rascunho de post para LinkedIn

No OpenAI Hackathon, trabalhei no Agende Bem — uma agenda inteligente para apoiar a recepção de clínicas após cancelamentos.

O desafio era transformar uma vaga liberada em uma decisão prática: importar a agenda, manter uma lista de espera, sugerir candidatos compatíveis e confirmar o encaixe sem criar conflitos.

Desenvolvi uma solução em Python e Streamlit com um motor determinístico que considera profissional, duração, disponibilidade, conflitos e tempo de espera. A decisão continua com a recepção, acompanhada de justificativas claras para candidatos elegíveis e inelegíveis.

Como evolução do MVP, a V3 incorporou PostgreSQL/Supabase, autenticação por papéis, histórico operacional e uma biblioteca privada de arquivos e modelos.

O principal aprendizado foi equilibrar regras de negócio, consistência transacional, experiência de uso e limites reais de infraestrutura serverless.

Projeto: https://agende-bem-demo.vercel.app
Código: https://github.com/ThiagoAlves-zc/Agendamento--Agende-bem

Autoria original do repositório: Thiago Alves. Evolução V3 registrada no histórico Git por Vitor Yoshii.
