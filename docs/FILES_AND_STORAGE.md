# Arquivos, modelos e Storage

## Escopo

A biblioteca armazena apenas arquivos operacionais sem dados pessoais: CSV e PDF de até 5 MB. Conteúdo fica em bucket privado; PostgreSQL guarda nome, categoria, hash, estado e referência ao objeto.

## Validação

`file_validation.py` rejeita nome com caminho ou caracteres de controle, arquivo vazio, tamanho acima do limite, extensão não permitida, MIME divergente, PDF sem assinatura e CSV fora de UTF-8. O objeto recebe chave UUID não previsível e SHA-256 é conferido no download.

## Modelos

O catálogo idempotente cria Agenda CSV, Lista de espera CSV, Profissionais CSV, Guia PDF e Relatório diário. Apenas Agenda CSV é documentado como compatível com a importação existente; os demais são referências até que haja importadores próprios.

## Falhas parciais

O upload ocorre antes dos metadados. Se a transação do PostgreSQL falhar, a aplicação tenta excluir o objeto recém-criado e preserva o erro principal. O processo não altera diretamente tabelas internas do schema `storage`.
