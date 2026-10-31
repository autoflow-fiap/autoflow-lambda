# Variables e secrets

Configure GitHub Environments separados chamados `homolog` e `production`, restritos respectivamente às branches `develop` e `main`. Plan e Apply são associados ao Environment selecionado pela branch, portanto recebem apenas suas credenciais, Variables e Secrets. Required reviewers são obrigatórios nos dois Environments e `TERRAFORM_APPLY_APPROVAL_CONFIGURED` deve ser `true` somente após confirmar a regra de aprovação.

Antes de promover para `main`, configure também branch protection com Pull Request obrigatório e checks de CI requeridos. Os jobs de Plan e Apply de produção exigem `github.ref_protected`; as regras do Environment protegem o deployment, mas não substituem a proteção da branch. Essa proteção externa permanece administrada fora do workflow.

O workflow `.github/workflows/ci.yml` executa CI automaticamente em Pull Requests para `develop`/`main` e pushes para `develop`, `main` e `feature/**`. O workflow `.github/workflows/pipeline.yml` aceita somente `workflow_dispatch` em `develop` ou `main`; `apply=false` permite Plan sem Apply, enquanto Apply requer `apply=true` e nova aprovação do Environment. Pushes e Pull Requests nunca iniciam chamadas AWS, Plan ou Apply. A região é fornecida pelo Environment e validada contra os recursos. Não cadastre `AWS_LAMBDA_FUNCTION_NAME`: o nome deriva do default Terraform `autoflow-cpf-validator` mais o ambiente (`-homolog` ou `-production`).

## GitHub Actions — Secrets

| Nome | Tipo / finalidade | Onde configurar; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Credenciais temporárias da mesma sessão AWS | Secrets separados em cada Environment; renovar em conjunto após expiração da sessão | Plan e Apply | Não aplicável | `.github/workflows/pipeline.yml`; obrigatórios e usados em `configure-aws-credentials`. |
| `DATABASE_USERNAME`, `DATABASE_PASSWORD` | Credenciais de conexão Lambda ao PostgreSQL do ambiente | Secrets separados em cada Environment; apontam ao RDS daquele ambiente | Plan e Apply/runtime | Não aplicável | Workflow → `TF_VAR_db_username/password` → Lambda; sem defaults, sensíveis. |
| `JWT_SECRET` | Chave HS256 usada pela Lambda para assinar JWT | Secret separado em cada Environment; deve ser igual a `AUTOFLOW_JWT_SECRET` da aplicação no mesmo ambiente | Plan e Apply/runtime | Não aplicável | Workflow → `TF_VAR_jwt_secret`; obrigatório, sem default; Terraform valida mínimo de 32 caracteres. |
| `TF_PLAN_ENCRYPTION_KEY` | Chave que cifra o artifact Terraform Plan | Secret separado em cada GitHub Environment | Plan e Apply | Não aplicável | Obrigatório no Environment; usado por OpenPGP para criptografar antes do upload e descriptografar no Apply aprovado. Não versionar nem imprimir. |

## GitHub Actions — Variables

| Nome | Finalidade | Onde; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_REGION` | Região AWS | Variable em cada Environment; valor `us-east-1` | Plan e Apply | `us-east-1` | Workflow/provider/backend; validação local do workflow exige a região definida pelo plano. |
| `AWS_EXPECTED_ACCOUNT_ID` | Conta esperada pelo guard | Variable independente em cada Environment | Plan e Apply | ID de conta configurado fora do repositório | Validado como 12 dígitos antes da autenticação e comparado à identidade STS antes de consultar recursos ou acessar State. |
| `AWS_TERRAFORM_STATE_BUCKET` | Bucket dos states e dos pacotes imutáveis | Variable em cada Environment; deve pertencer à conta esperada | Plan e Apply | Nome do bucket configurado para aquela conta | Workflow verifica o owner do bucket; Terraform usa o backend S3 e as referências remotas do mesmo bucket. |
| `AWS_TF_STATE_KEY` | Key exclusiva do State Terraform da Lambda | Variable em cada Environment; deve identificar o State autoritativo daquele root | Plan e Apply | `homolog/<key do State Lambda>`; `production/<key do State Lambda>` | Backend do workflow; o sufixo vem da configuração externa e deve ser distinto das keys remotas. |
| `AWS_INFRA_STATE_KEY` | Key do State VPC/EKS consumido | Variable em cada Environment; deve identificar o mesmo State configurado no root de infraestrutura | Plan e Apply | `homolog/<key VPC-EKS>`; `production/<key VPC-EKS>` | Deve ser igual a `AWS_TF_STATE_KEY_INFRA` do repositório `autoflow-infra`, no mesmo Environment. |
| `AWS_RDS_STATE_KEY` | Key do State RDS consumido | Variable em cada Environment; deve identificar o mesmo State configurado no root de banco | Plan e Apply | `homolog/<key RDS>`; `production/<key RDS>` | Deve ser igual a `AWS_TF_STATE_KEY` do repositório `autoflow-db` e a `AWS_RDS_STATE_KEY` de `autoflow`, no mesmo Environment. |
| `AWS_LAMBDA_EXECUTION_ROLE_ARN` | Role de execução Lambda | Variable independente em cada Environment; role aprovada para aquela conta | Plan e Apply | ARN cadastrado externamente, sem versioná-lo | Workflow → `TF_VAR_role_arn`; exige formato de ARN de role AWS com a mesma conta de `AWS_EXPECTED_ACCOUNT_ID` e não possui default no deploy. |
| `TERRAFORM_APPLY_APPROVAL_CONFIGURED` | Guard operacional adicional | Variable nos dois Environments; `true` só após configurar Required reviewers | Plan e Apply | `true` | Ausente/diferente bloqueia jobs; não substitui a aprovação nativa do Environment. |
| `AUTO_CD_ENABLED_HOMOLOG` | Habilita Plan automático após CI aprovada em homologação | Repository Variable; independente de produção | Gate de `push` em `develop` | `true` | Ausente ou diferente de `true` mantém homologação desabilitada. |
| `AUTO_CD_ENABLED_PRODUCTION` | Habilita Plan automático após CI aprovada em produção | Repository Variable; independente de homologação | Gate de `push` em `main` | `true` | Ausente ou diferente de `true` mantém produção desabilitada. |

As credenciais e configurações AWS acima não devem ser cadastradas como Repository Variables/Secrets compartilhadas entre ambientes. As duas Variables `AUTO_CD_ENABLED_*` são a exceção não sensível usada pelo gate sem Environment: elas mantêm opt-in independente por branch, enquanto os jobs de deploy continuam associados ao Environment selecionado. Em cada Environment, configure o mesmo `AWS_EXPECTED_ACCOUNT_ID` e bucket nos repositórios cujos States são consumidos entre si. O bucket deve pertencer à conta esperada. Em contas diferentes, cada Environment usa a conta e o bucket próprios, sem compartilhar States entre contas.

## Contrato de Terraform State entre repositórios

As keys são valores externos do GitHub Environment, não caminhos fixados no workflow. Todas devem usar o prefixo do Environment (`homolog/` ou `production/`), preservar o sufixo da key autoritativa existente e ser distintas entre roots que compartilham bucket. O workflow Lambda valida o prefixo e a unicidade entre o State próprio da Lambda e os States remotos de VPC/EKS e RDS. Plan e Apply também comparam um fingerprint do Environment, conta, bucket, keys, região, função e role para impedir que o Apply selecione configuração diferente do Plan.

| Root proprietário do State | Variable de key do proprietário | Variable consumida pela Lambda | Relação exigida no mesmo Environment |
|---|---|---|---|
| VPC/EKS (`autoflow-infra`) | `AWS_TF_STATE_KEY_INFRA` | `AWS_INFRA_STATE_KEY` | Os valores devem ser idênticos. |
| RDS (`autoflow-db`) | `AWS_TF_STATE_KEY` | `AWS_RDS_STATE_KEY` | Os valores devem ser idênticos; `autoflow` também deve consumir esse mesmo valor em `AWS_RDS_STATE_KEY`. |
| Lambda (`autoflow-lambda`) | `AWS_TF_STATE_KEY` | — | State próprio, distinto dos States de VPC/EKS e RDS. |
| Aplicação (`autoflow`) | `AWS_TF_STATE_KEY` | — | State próprio da aplicação, distinto dos demais roots no bucket compartilhado. |
| API Gateway e New Relic (`autoflow-infra`) | `AWS_TF_STATE_KEY_GATEWAY`, `AWS_TF_STATE_KEY_NEWRELIC` | — | Cada root usa key própria, distinta de VPC/EKS, RDS, Lambda e aplicação quando estiverem no mesmo bucket. |

O nome do root não determina o sufixo da key nesta documentação; confirme o valor autoritativo em cada Environment e mantenha exatamente o mesmo valor nas referências remotas. A configuração atual do Terraform da Lambda usa um único `AWS_TERRAFORM_STATE_BUCKET` para seu backend e para `terraform_remote_state`, portanto esse bucket precisa conter as keys de VPC/EKS e RDS do mesmo Environment e pertencer à conta esperada.

O backend S3 e os data sources `terraform_remote_state` usam `allowed_account_ids`, derivados de `AWS_EXPECTED_ACCOUNT_ID` fornecido pelo Environment. As chamadas AWS CLI mantêm `--expected-bucket-owner`; antes do init, o workflow verifica as keys remotas VPC/EKS e RDS com `head-object --expected-bucket-owner` na conta do Environment. Esse argumento de ownership não é passado à configuração Terraform.

### Risco de mudança de key e migração

O workflow/documentação anterior do PR #28 exigia paths fixos sem prefixo de Environment. Isso era uma regra local do repositório, não evidência da key existente na AWS. O State remoto não foi consultado nesta alteração. Se o valor atualmente configurado para um State existente ainda não tiver o prefixo exigido, alterá-lo diretamente faz o Terraform selecionar um backend vazio: a Lambda pode parecer não gerenciada e um Plan pode propor criação/recriação. O guard da Lambda bloqueia quando a função já existe sem State; a ausência de qualquer State remoto VPC/EKS ou RDS também interrompe o Plan antes de inicializar o backend. Esses guards evitam prosseguir, mas não substituem reconciliação/migração controlada do State. Não habilite o CD até confirmar que cada key prefixada já é autoritativa ou que a migração aprovada foi concluída.

O contrato da aplicação também exige prefixo por Environment e não possui default para a key RDS remota; o consumidor usa a mesma key publicada pelo root RDS. Cada correção permanece em sua branch/PR próprio. Esta documentação não comprova que os objetos S3 estejam reconciliados nem que qualquer pipeline tenha sido implantado.

## Terraform inputs — `infra/variables.tf`

| Input | Tipo / finalidade | Obrigatoriedade / default | Origem/consumidor |
|---|---|---|---|
| `region` | Região AWS | Opcional; `us-east-1` | GitHub `AWS_REGION` via `TF_VAR_region`. |
| `aws_profile` | Perfil AWS local | Opcional; `null` | Credenciais do processo; workflow não injeta. |
| `aws_allowed_account_ids` | Lista de contas autorizadas | Obrigatório; sem default; valida lista não vazia e IDs de 12 dígitos | Workflow deriva do `AWS_EXPECTED_ACCOUNT_ID` selecionado pelo Environment. |
| `environment` | Nome ambiente Lambda | Opcional; `homolog`; aceita `homolog`/`production` no Terraform | `develop` define `homolog`; `main` define `production`. |
| `lambda_name` | Nome base função | Opcional; `autoflow-cpf-validator` | Terraform. |
| `db_name` | Nome DB | Opcional; `autoflow_db` | Terraform/runtime. |
| `db_username`, `db_password` | Usuário e senha DB | Obrigatórios; sem defaults; sensíveis | Secrets `DATABASE_USERNAME/PASSWORD`. |
| `jwt_secret` | Segredo HS256 | Obrigatório; sem default; sensível; mínimo 32 caracteres | Secret `JWT_SECRET`. |
| `jwt_expires_in_seconds` | Duração JWT | Opcional; `3600`, deve ser > 0 | Terraform/runtime; handler tem fallback `3600`. |
| `role_arn` | Role de execução | Opcional `null` no Terraform | GitHub `AWS_LAMBDA_EXECUTION_ROLE_ARN`; obrigatório operacionalmente no workflow. |
| `terraform_state_bucket` | Bucket de states | Obrigatório; sem default | Workflow injeta o bucket do Environment selecionado; deve pertencer à conta esperada. |
| `infra_state_key`, `rds_state_key` | Keys remotas VPC/EKS e RDS | Obrigatórias, sem defaults para evitar selecionar implicitamente um State de outro ambiente | Variables `AWS_INFRA_STATE_KEY`, `AWS_RDS_STATE_KEY`; prefixadas pelo Environment, distintas e verificadas antes de Plan/Apply. |
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

`ci.yml` executa os testes estáticos sem credenciais AWS. Em `workflow_dispatch` com `apply=true`, `pipeline.yml` seleciona o Environment e, após autorização e aprovação, gera o ZIP e o publica antes do Plan no prefixo `lambda-packages/sha256/` do bucket daquele ambiente, usando PutObject condicional (`If-None-Match: *`). O helper exige Versioning habilitado, valida checksum SHA-256 e registra o VersionId. O Plan Terraform é criptografado com OpenPGP antes de ser publicado; o Apply aprovado confere integridade, Environment, run, attempt, commit, pacote, checksum, VersionId e fingerprint antes de descriptografar e aplicar exatamente o mesmo Plan. Um dispatch com `apply=false` gera somente o Plan, sem publicar o pacote ou aplicar recursos. O artifact é retido por um dia. Não se cria bucket ou recurso de pacote no State.

O prefixo de pacotes deve permanecer fora de regras de lifecycle que expirem os objetos enquanto planos puderem aguardar aprovação. A escrita condicional evita sobrescrever uma key existente; a role de CI não deve receber `s3:DeleteObject` ou `s3:DeleteObjectVersion` nesse prefixo. Habilite Versioning no bucket antes de usar o deploy. Se o bucket exigir SSE-KMS, conceda também as permissões KMS correspondentes ao principal do workflow.

Permissões S3 mínimas a conceder ao principal usado pelos jobs Plan/Apply: `s3:GetBucketVersioning` e `s3:GetBucketLocation` no bucket; `s3:PutObject` e `s3:GetObject` no prefixo `lambda-packages/sha256/*`. `s3:GetObjectVersion` também é necessário para leitura da versão referenciada pelo VersionId. O principal que chama `UpdateFunctionCode` deve ter acesso de leitura ao objeto versionado; a role de execução da Lambda não precisa dessa permissão para iniciar a função. Se o bucket usar SSE-KMS, verifique `kms:GenerateDataKey` e `kms:Decrypt` nas policies IAM e na key policy.

`lambda_package_key` usa o SHA-256 hexadecimal do mesmo ZIP cujo hash Base64 é enviado como `lambda_package_source_code_hash`. O script valida o objeto por checksum, tamanho e VersionId tanto antes do Plan quanto antes do Apply; se houver colisão de key com conteúdo diferente, versioning desabilitado ou expiração/ausência do objeto, o pipeline falha sem prosseguir.

**Diagnóstico do `bufio.Scanner: token too long`:** o `lambda.zip` medido neste checkout tem 4.574.589 bytes, abaixo do limite usual de upload ZIP inline da API Lambda. O lockfile local seleciona AWS provider `6.68.0`; ele não comprova qual binário foi usado no run que falhou. Há relato público de regressão com o mesmo erro em publicação inline Lambda no provider `6.69.0` ([issue #50474](https://github.com/hashicorp/terraform-provider-aws/issues/50474), relativo a Lambda Layer). Assim, o tamanho não demonstra excesso de quota e a versão exata do run permanece não confirmada; a fonte mais provável é o caminho de serialização do corpo ZIP no provider/SDK. O envio do objeto por S3 é um caminho suportado pela API Lambda e evita transportar o ZIP inline na chamada `UpdateFunctionCode`.

`DATABASE_USERNAME/PASSWORD` são os nomes dos GitHub Secrets; o workflow os mapeia para `db_username/password` e o Terraform configura `DB_USERNAME/PASSWORD` no runtime. O `JWT_SECRET` da Lambda deve ser idêntico ao `AUTOFLOW_JWT_SECRET` da aplicação no Environment correspondente. O nome da função é derivado de `lambda_name` e `environment`; não há configuração manual de nome nem dependência da conta AWS de origem.

**Fontes:** `.github/workflows/pipeline.yml`, `infra/variables.tf`, `infra/lambda.tf`, `handler.py`, `build.sh`, `README.md`.
