# Início automático do CD

O workflow de CD recebe `push` em `develop` ou `main`, mas seu gate consulta e aguarda a execução de `.github/workflows/ci.yml` para a mesma branch e o mesmo SHA. Somente a conclusão `success` da CI exata libera o Plan. As Repository Variables independentes `AUTO_CD_ENABLED_HOMOLOG` e `AUTO_CD_ENABLED_PRODUCTION` controlam o início automático de cada ambiente: somente o valor literal `true` habilita o respectivo gate; variável ausente ou qualquer outro valor mantém o ambiente desabilitado. O gate recebe esses valores diretamente pelo contexto `vars` e não consulta a API administrativa dos Environments. Nenhuma variável, Secret, Environment ou regra de proteção é criada por este código.

O gate usa o token padrão com leitura de Actions para consultar a API do GitHub por até 30 minutos. Ele confirma o nome `Lambda CI`, o evento `push`, o repositório, a branch, o SHA e a conclusão. Ausência de execução, falha, cancelamento, conclusão `skipped`, divergência ou timeout bloqueia o Plan. O token é usado somente para ler execuções de CI; o controle opt-in vem das Variables injetadas no job. O checkout usa o SHA validado e compara `git rev-parse HEAD` antes de acessar AWS. PRs e branches `feature/**` não são gatilhos. `main` também precisa estar protegida.

O gate recebe as Repository Variables independentes `AUTO_CD_ENABLED_HOMOLOG` e `AUTO_CD_ENABLED_PRODUCTION`; valor ausente ou diferente de `true` mantém o ambiente desabilitado. Quando habilitado, o caminho automático espera sucesso da CI para o mesmo SHA e executa Plan. O Plan publica um pacote Lambda imutável no S3 antes do Terraform Plan, mas não aplica Terraform nem atualiza a função.

Apply continua disponível somente por `workflow_dispatch` com `apply=true` e `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`. O job usa o GitHub Environment selecionado; configure Required reviewers e restrições de branch para proteger o deployment. A aprovação de um Plan não autoriza Apply.

## Configuração externa

- Para habilitar homologação, definir a Repository Variable `AUTO_CD_ENABLED_HOMOLOG=true`; para produção, definir separadamente `AUTO_CD_ENABLED_PRODUCTION=true`. Valor ausente ou diferente de `true` mantém o respectivo ambiente desabilitado.
- Repetir a configuração somente nos repositórios e ambientes que se queira habilitar.
- São duas Variables não sensíveis acessíveis ao gate, que roda sem Environment; não exigem Secret novo nem ID de conta. As credenciais AWS, States, criptografia e gates continuam separados nos GitHub Environments `homolog` e `production`.

O gate automático apenas inicia os jobs de Plan após a CI aprovada. As proteções próprias do Environment continuam aplicáveis. Nenhuma implantação ou operação AWS é inferida como realizada por esta configuração local.
