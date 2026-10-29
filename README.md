# Lambda de autenticação do AutoFlow

Este repositório mantém a função serverless Python 3.12 que autentica clientes pelo PostgreSQL e emite JWT HS256. O fluxo declarado é **Frontend Angular → Amazon API Gateway HTTP API → integração AWS_PROXY → Lambda → RDS PostgreSQL**. O backend Spring Boot valida o JWT nas rotas protegidas. O AWS Academy Learner Lab foi resetado; esta descrição não comprova recursos ativos ou runtime após o reset.

O repositório `autoflow-infra` declara a integração nativa e a permissão `lambda:InvokeFunction` restrita à rota de login. O Terraform deste repositório gerencia somente a função e sua configuração de execução. O registro anterior ao reset descreve a remoção da Function URL legada e das duas permissões públicas; o estado atual precisa ser verificado após recriar a infraestrutura.

## Fluxo de autenticação CPF/JWT

O API Gateway HTTP API v2 encaminha a solicitação de login à Lambda por integração `AWS_PROXY`. A função valida o CPF/CNPJ, consulta usuário e cliente no PostgreSQL, verifica a senha com BCrypt e emite um JWT HS256. Para o perfil `CLIENTE`, o cliente associado precisa estar ativo. O backend Spring Boot valida assinatura e claims e carrega o perfil atual antes de autorizar rotas protegidas.

```mermaid
flowchart LR
  Browser[Navegador / Angular] -->|Login CPF/CNPJ| Gateway[Amazon API Gateway HTTP API v2]
  Gateway -->|AWS_PROXY payload 2.0| Lambda[Lambda Python 3.12]
  Lambda -->|consulta e valida credenciais| DB[(PostgreSQL RDS)]
  Lambda -->|JWT HS256| Browser
  Browser -->|Bearer JWT| Gateway
  Gateway -->|Rotas de negócio / VPC Link| ALB[ALB interno]
  ALB --> Backend[Backend Spring Boot no EKS]
  Backend -->|validação JWT e dados de negócio| DB
```

Os corpos, respostas, status HTTP e exemplos de requisição são mantidos no [guia central OpenAPI](https://github.com/BrunoSousa06/autoflow/blob/develop/docs/openapi/README.md) e na [coleção Postman de autenticação CPF/JWT](https://github.com/BrunoSousa06/autoflow/blob/develop/backend/postman/autoflow-serverless-auth.postman_collection.json); este README não duplica o contrato. `JWT_SECRET` precisa corresponder entre Lambda e backend.

O API Gateway e a permissão de invocação são mantidos em `autoflow-infra`; esta função conecta-se ao RDS privado. O diagrama mostra a configuração declarada e não implica disponibilidade atual de API Gateway, Lambda, EKS ou RDS.

## Terraform e segurança

`infra/lambda.tf` declara a função existente em subnets privadas, Security Group do RDS, timeout de 15 segundos e memória de 256 MB. A role de execução é fornecida externamente. O ZIP é publicado no bucket S3 existente sob `lambda-packages/sha256/`, com escrita condicional, versionamento e checksum; o Terraform usa bucket, chave e `VersionId` aprovados no Plan. O prefixo dos pacotes não coincide com as keys dos Terraform States. A identidade e a configuração de runtime da função permanecem gerenciadas pelo mesmo recurso Terraform.

O plan de retirada da URL deve conter somente a destruição de `aws_lambda_function_url.cpf_validator[0]` e dos dois statements públicos legados. Não deve atualizar `aws_lambda_function.cpf_validator` nem remover a permissão nativa do API Gateway. O plano é aprovado separadamente antes do Apply; não recrie a URL ou permissões públicas.

O checkpoint registra que, em 13/10/2026, `lambda.zip` e `handler.py` foram sincronizados com o pacote implantado, sem publicar atualização da função. Essa é uma evidência registrada naquela data, não uma verificação do artefato AWS atual. Alterações de código devem ser planejadas separadamente e não inferidas do workflow de Terraform.

## Pipeline e validação

Consulte o [catálogo de variables e secrets](docs/variables-and-secrets.md) e o [histórico](docs/variables-changelog.md) para configuração do GitHub Actions, Terraform e runtime.

CI executa em Pull Requests e pushes para `develop` e `main`, com testes Python, auditoria de dependências e validação Terraform. O workflow declara Plan/Apply de homologação em push ou `workflow_dispatch` na branch `develop`, com Apply no Environment `homolog`; Required reviewers precisam estar configurados no GitHub, e a variable `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true` é um guard adicional. A configuração efetiva dos reviewers e a execução do workflow não foram verificadas. O AWS Academy Learner Lab foi resetado, portanto o código do pipeline não comprova recursos implantados. Não há Apply em PR nem CD de produção.

Configure como repository secrets os secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `DATABASE_USERNAME`, `DATABASE_PASSWORD` e `JWT_SECRET`; como repository variables `AWS_REGION`, `AWS_EXPECTED_ACCOUNT_ID`, `AWS_TERRAFORM_STATE_BUCKET`, `AWS_TF_STATE_KEY`, `AWS_INFRA_STATE_KEY`, `AWS_RDS_STATE_KEY` e `AWS_LAMBDA_EXECUTION_ROLE_ARN`; e como Environment variable `homolog`, `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`. O bucket de pacotes Lambda reutiliza `AWS_TERRAFORM_STATE_BUCKET`. Configure Required reviewers no Environment `homolog`. Os valores esperados estão documentados em [variables-and-secrets.md](docs/variables-and-secrets.md); não copie valores sensíveis para documentação.

```bash
# Pré-requisito: Python 3.12
python -m pip install -r requirements.txt
python -m unittest discover -s . -p "test_*.py" -v
```

Para criar localmente o pacote de deploy determinístico, use Docker e Bash (por exemplo, Git Bash ou WSL):

```bash
bash build.sh
```

O pipeline versionado publica o pacote e executa Terraform para homologação. Para solicitar a execução manual, selecione a branch `develop` no workflow `Pipeline` e use `workflow_dispatch`; revise o Plan e o gate do Environment `homolog` antes de qualquer Apply. Após o reset do Learner Lab, credenciais, states e recursos devem ser confirmados pelo owner autorizado. Este repositório não declara deploy de produção.

Para validar o Terraform sem acessar o backend remoto:

```bash
cd infra
terraform init -backend=false -input=false
terraform validate
```

O state S3 e os states remotos consumidos devem ser os autorizados para a conta e ambiente esperados. Não aplique planos que incluam alteração de código Lambda durante o fechamento da URL.
