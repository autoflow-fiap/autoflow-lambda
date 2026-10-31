# Início automático do CD

O workflow de CD recebe `push` em `develop` ou `main`, mas seu gate consulta e aguarda a execução de `.github/workflows/ci.yml` para a mesma branch e o mesmo SHA. Somente a conclusão `success` da CI exata libera o Plan. A Variable externa `AUTO_CD_ENABLED`, no Environment de destino, controla o início automático: somente o valor literal `true` habilita o gate; variável ausente ou qualquer outro valor o mantém desabilitado. Nenhuma variável, Secret, Environment ou regra de proteção é criada por este código.

O gate usa o token padrão com leitura de Actions para consultar a API do GitHub por até 30 minutos. Ele confirma o nome `Lambda CI`, o evento `push`, o repositório, a branch, o SHA e a conclusão. Ausência de execução, falha, cancelamento, conclusão `skipped`, divergência ou timeout bloqueia o Plan. O checkout usa o SHA validado e compara `git rev-parse HEAD` antes de acessar AWS. PRs e branches `feature/**` não são gatilhos. `main` também precisa estar protegida.

Foi escolhido `push` com espera e validação da CI por API, em vez de `workflow_run`, porque a branch padrão deste repositório é `main`, enquanto o PR desta entrega tem destino `develop`. Assim o CD continua definido na branch alvo e não precisa de `actions:write` nem de token para re-disparo. `AUTO_CD_ENABLED` pode ser configurada separadamente nos Environments `homolog` e `production`; ausente ou diferente de `true` não libera Plan, publicação de pacote ou operação AWS. O Plan automático continua protegido pelo Environment selecionado. O Plan atual publica um pacote Lambda imutável no S3 como etapa necessária; essa aprovação de Environment não executa Apply. O marcador `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true` é verificado separadamente no Apply.

O caminho automático executa somente o Plan. Apply continua disponível somente por `workflow_dispatch` com `apply=true`, aprovação efetiva de Required Reviewers no Environment selecionado e `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`. A aprovação de Environment para um Plan não autoriza o Apply, que exige execução separada e nova autorização. O fluxo manual Plan-only permanece disponível com `apply=false`.

## Configuração externa

- Para habilitar homologação, criar fora deste PR a Variable `AUTO_CD_ENABLED=true` no Environment `homolog`; para habilitar produção, criá-la separadamente em `production`. Variável ausente ou diferente de `true` mantém o ambiente desabilitado.
- Repetir a configuração somente nos repositórios e ambientes que se queira habilitar.
- A configuração exige apenas uma Variable não sensível; não exige Secret novo nem ID de conta. O CD continua reutilizando as configurações AWS, States, criptografia e gates existentes em cada Environment.

O gate automático apenas inicia os jobs de Plan após a CI aprovada. As proteções próprias do Environment continuam aplicáveis. Nenhuma implantação ou operação AWS é inferida como realizada por esta configuração local.
