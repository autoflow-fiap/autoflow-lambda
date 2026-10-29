# Integração Lambda com Amazon API Gateway

> Os registros operacionais abaixo são anteriores ao reset do AWS Academy Learner Lab. Eles não comprovam o estado atual; validar novamente somente após recriar a infraestrutura.

O API Gateway HTTP API gerenciado em `autoflow-infra/infra/api-gateway` chama `POST /auth/login` pela integração nativa `AWS_PROXY`, payload `2.0`. A permissão `lambda:InvokeFunction` pertence ao state do API Gateway e é limitada à conta e à rota. Não há integração por Function URL.

## Homologação observada

Antes do fechamento da Function URL em 13/10/2026, login fictício inválido e payloads inválidos foram testados pelo endpoint HTTP API. Um cliente seed ativo autenticou com HTTP 200 e o JWT emitido foi aceito por uma consulta protegida do backend, também HTTP 200. Após o fechamento, o smoke confirmou novamente a integração nativa, respostas negativas e saúde da infraestrutura; o fluxo positivo ainda precisa ser repetido quando as credenciais seed estiverem disponíveis no ambiente. Credenciais e tokens são mantidos somente em memória e não fazem parte da documentação.

## Reconciliação do artefato

O pacote `lambda.zip` local foi sincronizado byte a byte com o pacote implantado, após preservar o ZIP local anterior fora do repositório. A função implantada e o ZIP sincronizado têm os mesmos membros; `handler.py` é o único membro relevante do pacote.

O `handler.py` fonte local corresponde semanticamente ao handler do pacote implantado; a comparação do pacote não encontrou arquivos divergentes. Ambos consomem `cpf_cnpj` e tratam eventos HTTP API v2. Nenhuma atualização da função foi feita; o pipeline preserva o ZIP implantado quando fecha a Function URL.

## Function URL removida

A Function URL não participa do caminho de autenticação e foi removida em homologação com um Plan de 0 add / 0 change / 3 destroy (URL e duas permissões públicas), sem atualizar `aws_lambda_function`. A consulta posterior confirmou que a URL não existe e que a permissão nativa do API Gateway permanece. O Plan aplicado é local e ignorado pelo Git; não deve ser versionado ou publicado.

O smoke pós-Apply validou o login negativo e o contrato da integração. Para repetir login positivo, emissão de JWT e consulta protegida, disponibilize `AUTOFLOW_TEST_CPF_CNPJ` e `AUTOFLOW_TEST_PASSWORD` de um cliente seed ativo no ambiente local, sem registrar os valores.
