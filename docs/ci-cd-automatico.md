# Início automático do CD

O workflow de CD recebe `push` em `develop` ou `main`, mas seu gate consulta e aguarda a execução de `.github/workflows/ci.yml` para a mesma branch e o mesmo SHA. Somente a conclusão `success` da CI exata libera o Plan. As Repository Variables independentes `AUTO_CD_ENABLED_HOMOLOG` e `AUTO_CD_ENABLED_PRODUCTION` controlam o início automático de cada ambiente: somente o valor literal `true` habilita o respectivo gate; variável ausente ou qualquer outro valor mantém o ambiente desabilitado. O gate recebe esses valores diretamente pelo contexto `vars` e não consulta a API administrativa dos Environments. Nenhuma variável, Secret, Environment ou regra de proteção é criada por este código.

O gate usa o token padrão com leitura de Actions para consultar a API do GitHub por até 30 minutos. Ele confirma o nome `Lambda CI`, o evento `push`, o repositório, a branch, o SHA e a conclusão. Ausência de execução, falha, cancelamento, conclusão `skipped`, divergência ou timeout bloqueia o Plan. O token é usado somente para ler execuções de CI; o controle opt-in vem das Variables injetadas no job. O checkout usa o SHA validado e compara `git rev-parse HEAD` antes de acessar AWS. PRs e branches `feature/**` não são gatilhos. `main` também precisa estar protegida.

Foi escolhido `push` com espera e validação da CI por API, em vez de `workflow_run`, porque a branch padrão deste repositório é `main`, enquanto o PR desta entrega tem destino `develop`. Assim o CD continua definido na branch alvo e não precisa de `actions:write` nem de token para re-disparo. `AUTO_CD_ENABLED_HOMOLOG` e `AUTO_CD_ENABLED_PRODUCTION` são Repository Variables distintas; ausente ou diferente de `true` não libera o Plan, a publicação de pacote nem a operação AWS do respectivo ambiente. O Plan automático continua protegido pelo Environment selecionado. O Plan atual publica um pacote Lambda imutável no S3 como etapa necessária; essa aprovação de Environment não executa Apply. O marcador `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true` é verificado separadamente no Apply.

O caminho automático executa somente o Plan. Apply continua disponível somente por `workflow_dispatch` com `apply=true`, aprovação efetiva de Required Reviewers no Environment selecionado e `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`. A aprovação de Environment para um Plan não autoriza o Apply, que exige execução separada e nova autorização. O fluxo manual Plan-only permanece disponível com `apply=false`.

## Configuração externa

- Para habilitar homologação, definir a Repository Variable `AUTO_CD_ENABLED_HOMOLOG=true`; para habilitar produção, definir separadamente `AUTO_CD_ENABLED_PRODUCTION=true`. Valor ausente ou diferente de `true` mantém o respectivo ambiente desabilitado.
- Repetir a configuração somente nos repositórios e ambientes que se queira habilitar.
- São duas Variables não sensíveis no nível do repositório; não exigem Secret novo nem ID de conta. As credenciais AWS, States, criptografia e gates continuam separados nos GitHub Environments `homolog` e `production`.

O gate automático apenas inicia os jobs de Plan após a CI aprovada. As proteções próprias do Environment continuam aplicáveis. Nenhuma implantação ou operação AWS é inferida como realizada por esta configuração local.
