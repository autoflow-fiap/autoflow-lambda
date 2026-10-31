# Lambda de autenticação do AutoFlow

Este repositório mantém a função AWS Lambda em Python 3.12 que autentica usuários por CPF/CNPJ e emite JWT HS256. A
função consulta o RDS PostgreSQL; o backend Spring Boot valida o token e aplica autorização nas rotas de negócio.

## Papel na arquitetura

`autoflow-infra` gerencia a Amazon API Gateway HTTP API v2, sua integração `AWS_PROXY` e a permissão de invocação da
Lambda. O Terraform deste repositório gerencia a função e sua execução em rede privada. O login não usa Function URL.

```mermaid
flowchart LR
  Browser[Navegador / Angular] -->|POST /auth/login| Gateway[API Gateway HTTP API v2]
  Gateway -->|AWS_PROXY — payload 2.0| Lambda[Lambda Python 3.12]
  Lambda -->|consulta usuário, senha e status| DB[(RDS PostgreSQL)]
  Lambda -->|JWT HS256| Browser
  Browser -->|rotas de negócio + Bearer JWT| Gateway
  Gateway -->|VPC Link| ALB[ALB interno]
  ALB --> Backend[Spring Boot no EKS]
  Backend -->|valida JWT e acessa dados| DB
```

A função normaliza e valida CPF/CNPJ, verifica a senha com BCrypt e consulta o usuário no PostgreSQL. Para o perfil
`CLIENTE`, também exige cliente ativo. O backend revalida assinatura e claims e carrega o perfil atual do banco; a HTTP API
não atua como JWT authorizer.

O contrato e exemplos estão no [guia OpenAPI](https://github.com/autoflow-fiap/autoflow/blob/develop/docs/openapi/README.md)
e na [coleção Postman de autenticação](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/postman/autoflow-serverless-auth.postman_collection.json).
O README de [integração com API Gateway](docs/api-gateway.md) e o [catálogo de Variables e Secrets](docs/variables-and-secrets.md)
detalham a configuração.

## Validar e empacotar localmente

Requer Python 3.12, Terraform 1.16.5 e Bash (Git Bash ou WSL para o build do pacote):

```bash
python -m pip install -r requirements.txt
python -m unittest test_handler test_http_api -v
python -m unittest discover -s scripts -p 'test_*.py' -v
bash build.sh
terraform -chdir=infra init -backend=false -input=false
terraform -chdir=infra validate
```

`build.sh` gera o pacote ZIP; Dockerfile não se aplica a este runtime Lambda. Os comandos Terraform acima não usam backend
remoto nem acessam a AWS.

## CI/CD e ambientes

- `ci.yml` executa testes Python, auditoria de dependências, build do pacote e validação Terraform em PRs para
  `develop`/`main` e pushes para `develop`, `main` e `feature/**`.
- `pipeline.yml` recebe `push` e `workflow_dispatch` em `develop`/`main`. O caminho automático aguarda sucesso de `Lambda CI`
  para o mesmo SHA e exige `AUTO_CD_ENABLED=true` no Environment. Na leitura somente-leitura do GitHub em 31/10/2026,
  essa Variable estava ausente em `homolog` e `production`, então o caminho automático estava desabilitado.
- Cada Plan publica um pacote Lambda imutável no S3 antes de gerar o Terraform Plan; isso inclui o caminho automático e
  o dispatch Plan-only (`apply=false`). Esse passo não aplica Terraform nem atualiza a função.
- O Apply só ocorre por `workflow_dispatch` com `apply=true`, após aprovação independente do Environment e validações do
  Plan. `TERRAFORM_APPLY_APPROVAL_CONFIGURED` estava `false` nos dois Environments, bloqueando Apply. `develop` seleciona
  `homolog`; `main` seleciona `production` e requer `github.ref_protected=true`.
- Regrasets ativos exigiam Pull Request e checks em `develop` e `main`; os Environments tinham Required reviewers e
  políticas de branch correspondentes. Isso foi verificado somente-leitura no GitHub em 31/10/2026.
- `pr-automatico.yaml` abre Pull Request para `develop` conforme os filtros do workflow.

O fluxo depende dos States de VPC/EKS e RDS do mesmo ambiente, do bucket S3 configurado e da role de execução Lambda. A
API Gateway é provisionada pelo root correspondente em `autoflow-infra`, na sequência descrita no
[runbook de implantação](https://github.com/autoflow-fiap/autoflow-infra/blob/develop/docs/api-gateway/runbook.md).

## Estado da evidência

**Implementado:** função, Terraform e workflows. **Validado:** a [Lambda CI](https://github.com/autoflow-fiap/autoflow-lambda/actions/runs/41160356788)
concluiu com sucesso; a [Lambda Pipeline](https://github.com/autoflow-fiap/autoflow-lambda/actions/runs/41160356791) falhou
no gate antes do Plan. **Implantado:** não comprovado; não há evidência nesta revisão de Apply ou de função Lambda ativa,
e nenhum endpoint de login é publicado como ativo.
