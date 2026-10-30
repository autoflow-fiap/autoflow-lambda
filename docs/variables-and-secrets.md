# Variables e secrets

Após reset do Learner Lab, configure credenciais temporárias, `AWS_REGION`, `AWS_EXPECTED_ACCOUNT_ID`, bucket/keys dos states e do pacote, role de execução Lambda e secrets de banco/JWT. O state Lambda e as referências remotas existentes são validados antes do Plan; não cadastre `AWS_LAMBDA_FUNCTION_NAME`, pois o workflow usa a composição `autoflow-cpf-validator-homolog` definida pelos defaults Terraform.

Catálogo necessário para o workflow versionado. CI em PR/push roda sem AWS credentials; o plan automático não entra no Environment para não aguardar aprovação. Portanto, configure as variables e secrets AWS/runtime como configurações do repositório (disponíveis nos jobs), ou use secrets/variables de organização acessíveis ao repositório. O job Apply entra no Environment `homolog`, que deve ter Required reviewers configurados. A aprovação nativa é a barreira do job `environment: homolog`; a variable de aprovação abaixo é somente um guard adicional.

## GitHub Actions — Secrets

| Nome | Tipo / finalidade | Onde configurar; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Secrets; credenciais temporárias da mesma sessão AWS | Repository secrets (ou organização acessível ao repositório); sessão AWS Academy Learner Lab | Plan e Apply | Não aplicável | `.github/workflows/pipeline.yml`; obrigatórios e usados em `configure-aws-credentials`. |
| `DATABASE_USERNAME`, `DATABASE_PASSWORD` | Secrets; credenciais de conexão DB Lambda | Repository secrets (ou organização acessível ao repositório); credenciais do usuário de homolog | Plan e Apply/runtime | Não aplicável | Workflow → `TF_VAR_db_username/password` → Lambda; sem defaults, sensíveis. |
| `JWT_SECRET` | Secret; chave HS256 de assinatura JWT | Repository secret (ou organização acessível ao repositório); segredo compatível com backend | Plan e Apply/runtime | Não aplicável | Workflow → `TF_VAR_jwt_secret`; obrigatório, sem default; Terraform valida mínimo de 32 caracteres. |

## GitHub Actions — Variables

| Nome | Finalidade | Onde; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_REGION` | Região AWS | Repository variable | Plan e Apply | `us-east-1` | Workflow/provider/backend; validada contra a região esperada. |
| `AWS_EXPECTED_ACCOUNT_ID` | Conta esperada pelo guard | Repository variable | Plan e Apply | Identificador AWS de 12 dígitos fornecido externamente | Workflow compara com `sts get-caller-identity` e deriva a allowlist do backend e dos states remotos. |
| `AWS_TERRAFORM_STATE_BUCKET` | Bucket de states Terraform | Repository variable | Plan e Apply | Nome exclusivo configurado para a conta/região | Workflow/backend; bootstrap separado e explicitamente aprovado quando ausente. |
| `AWS_TF_STATE_KEY` | Key state próprio Lambda | Repository variable | Plan e Apply | `lambda/terraform.tfstate` | Backend do workflow; validada e preservada. |
| `AWS_INFRA_STATE_KEY`, `AWS_RDS_STATE_KEY` | Keys remotas EKS e RDS | Repository variables | Plan e Apply | `eks/terraform.tfstate`; `rds/terraform.tfstate` | Workflow valida objetos e Terraform lê data sources; preservadas. |
| `AWS_LAMBDA_EXECUTION_ROLE_ARN` | Role de execução Lambda | Repository variable; ARN aprovado | Plan e Apply | ARN da role aprovada na conta configurada | Workflow → `TF_VAR_role_arn`; valida não vazio. |
| `TERRAFORM_APPLY_APPROVAL_CONFIGURED` | Guard operacional adicional | Environment variable `homolog`; `true` somente após configurar Required reviewers | Apply | `true` | Ausente/diferente bloqueia Apply; não substitui a proteção nativa do Environment. |

## Terraform inputs — `infra/variables.tf`

| Input | Tipo / finalidade | Obrigatoriedade / default | Origem/consumidor |
|---|---|---|---|
| `region` | Região AWS | Opcional; `us-east-1` | GitHub `AWS_REGION` via `TF_VAR_region`. |
| `aws_profile` | Perfil AWS local | Opcional; `null` | Credenciais do processo; workflow não injeta. |
| `aws_allowed_account_ids` | Lista de contas autorizadas | Obrigatório; sem default; valida lista não vazia e IDs de 12 dígitos | Workflow transforma `AWS_EXPECTED_ACCOUNT_ID` em lista. |
| `environment` | Nome ambiente Lambda | Opcional; `homolog`; aceita homolog/production no Terraform | Workflow fixa `TF_VAR_environment=homolog`. |
| `lambda_name` | Nome base função | Opcional; `autoflow-cpf-validator` | Terraform. |
| `db_name` | Nome DB | Opcional; `autoflow_db` | Terraform/runtime. |
| `db_username`, `db_password` | Usuário e senha DB | Obrigatórios; sem defaults; sensíveis | Secrets `DATABASE_USERNAME/PASSWORD`. |
| `jwt_secret` | Segredo HS256 | Obrigatório; sem default; sensível; mínimo 32 caracteres | Secret `JWT_SECRET`. |
| `jwt_expires_in_seconds` | Duração JWT | Opcional; `3600`, deve ser > 0 | Terraform/runtime; handler tem fallback `3600`. |
| `role_arn` | Role de execução | Opcional `null` no Terraform | GitHub `AWS_LAMBDA_EXECUTION_ROLE_ARN`; obrigatório operacionalmente no workflow. |
| `terraform_state_bucket` | Bucket de states | Obrigatório; sem default | Workflow injeta `AWS_TERRAFORM_STATE_BUCKET`; todos os roots usam o mesmo bucket externo. |
| `infra_state_key`, `rds_state_key` | Keys remotas | Defaults `infra/terraform.tfstate`, `rds/terraform.tfstate` | Variables GitHub `AWS_INFRA_STATE_KEY`, `AWS_RDS_STATE_KEY`; checadas pelo workflow. |
| `lambda_package_bucket` | Bucket S3 existente dos pacotes | Obrigatório; reutiliza `AWS_TERRAFORM_STATE_BUCKET` | `aws_lambda_function.cpf_validator.s3_bucket`; exige região compatível e Versioning habilitado. |
| `lambda_package_key` | Key S3 derivada do SHA-256 hexadecimal | Obrigatório; formato `lambda-packages/sha256/<sha256>.zip` | `aws_lambda_function.cpf_validator.s3_key`. |
| `lambda_package_source_code_hash` | SHA-256 do ZIP em Base64 | Obrigatório; calculado pelo script de publicação | `aws_lambda_function.cpf_validator.source_code_hash`. |
| `lambda_package_version` | VersionId do objeto S3 | Obrigatório; recebido da publicação Plan e salvo no plan/artifact | `aws_lambda_function.cpf_validator.s3_object_version`. |

## Runtime da função e configuração local

| Nome | Tipo / finalidade | Onde configurar; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `DB_HOST` | Variável de aplicação; host PostgreSQL | Variáveis de ambiente Lambda/local; output do state RDS | CI não; CD/runtime | `db.example.invalid` | `handler.py`; obrigatória, acesso direto `os.environ`. |
| `DB_PORT`, `DB_NAME` | Variáveis de aplicação; porta e database | Runtime/local | CI não; CD/runtime | `5432`, `autoflow_db` | `handler.py`; defaults `5432`, `autoflow_db`. Terraform input `db_name` define o database. |
| `DB_USERNAME`, `DB_PASSWORD` | Variáveis de aplicação; autenticação DB | Runtime derivado do Secret; local via ambiente seguro | CI não; CD/runtime | Não aplicável | `handler.py`; obrigatórias. GitHub usa `DATABASE_USERNAME/PASSWORD`, Terraform recebe `db_username/password` e configuração Lambda usa nomes `DB_*`. |
| `JWT_SECRET`, `JWT_EXPIRES_IN_SECONDS` | Variáveis de aplicação; assinatura e duração JWT | Runtime Lambda/local seguro | CI não; CD/runtime | Não aplicável; `3600` | `handler.py`; segredo obrigatório, duração default `3600`; alinhamento de segredo com backend necessário. |

`pipeline.yml` executa CI em PRs para `develop`/`main` e pushes nessas branches. Push em `develop` gera o ZIP, publica-o antes do Plan no prefixo `lambda-packages/sha256/` do bucket Terraform State existente e usa PutObject condicional (`If-None-Match: *`). O helper exige Versioning habilitado, valida o checksum SHA-256 nativo e registra o VersionId. O Terraform recebe bucket, key, hash e VersionId como variáveis; o Apply usa o plan salvo que fixa essa mesma versão S3 e valida novamente pacote, checksum e VersionId após a aprovação do Environment `homolog`. O artifact (plan, ZIP e metadados) é confidencial e retido por um dia. Não se cria bucket ou recurso de pacote no state, e as keys dos Terraform States permanecem inalteradas.

O prefixo de pacotes deve permanecer fora de regras de lifecycle que expirem os objetos enquanto planos puderem aguardar aprovação. A escrita condicional evita sobrescrever uma key existente; a role de CI não deve receber `s3:DeleteObject` ou `s3:DeleteObjectVersion` nesse prefixo. Habilite Versioning no bucket antes de usar o deploy. Se o bucket exigir SSE-KMS, conceda também as permissões KMS correspondentes ao principal do workflow.

Permissões S3 mínimas a conceder ao principal usado pelos jobs Plan/Apply: `s3:GetBucketVersioning` e `s3:GetBucketLocation` no bucket; `s3:PutObject` e `s3:GetObject` no prefixo `lambda-packages/sha256/*`. `s3:GetObjectVersion` também é necessário para leitura da versão referenciada pelo VersionId. O principal que chama `UpdateFunctionCode` deve ter acesso de leitura ao objeto versionado; a role de execução da Lambda não precisa dessa permissão para iniciar a função. Se o bucket usar SSE-KMS, verifique `kms:GenerateDataKey` e `kms:Decrypt` nas policies IAM e na key policy.

`lambda_package_key` usa o SHA-256 hexadecimal do mesmo ZIP cujo hash Base64 é enviado como `lambda_package_source_code_hash`. O script valida o objeto por checksum, tamanho e VersionId tanto antes do Plan quanto antes do Apply; se houver colisão de key com conteúdo diferente, versioning desabilitado ou expiração/ausência do objeto, o pipeline falha sem prosseguir.

**Diagnóstico do `bufio.Scanner: token too long`:** o `lambda.zip` medido neste checkout tem 4.574.589 bytes, abaixo do limite usual de upload ZIP inline da API Lambda. O lockfile local seleciona AWS provider `6.68.0`; ele não comprova qual binário foi usado no run que falhou. Há relato público de regressão com o mesmo erro em publicação inline Lambda no provider `6.69.0` ([issue #50474](https://github.com/hashicorp/terraform-provider-aws/issues/50474), relativo a Lambda Layer). Assim, o tamanho não demonstra excesso de quota e a versão exata do run permanece não confirmada; a fonte mais provável é o caminho de serialização do corpo ZIP no provider/SDK. O envio do objeto por S3 é um caminho suportado pela API Lambda e evita transportar o ZIP inline na chamada `UpdateFunctionCode`.

**Divergências:** os secrets `DATABASE_USERNAME/PASSWORD` são mapeados para Terraform `db_username/password`, mas o runtime Lambda lê `DB_USERNAME/PASSWORD`. Terraform `environment` aceita `production`, enquanto o workflow fixa `homolog`; essa aceitação no código não habilita deploy de produção. `terraform_state_bucket` é obrigatório e os workflows recebem o bucket compartilhado por `AWS_TERRAFORM_STATE_BUCKET`. O workflow do API Gateway também valida a função `autoflow-cpf-validator-homolog` sem variable manual.

**Fontes:** `.github/workflows/pipeline.yml`, `infra/variables.tf`, `infra/lambda.tf`, `handler.py`, `build.sh`, `README.md`.
