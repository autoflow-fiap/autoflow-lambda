# Progresso da implementação — produção dedicada da Lambda

Referência: seção `autoflow-lambda` de `AutoFlow_Fase3_Plano_Producao_Dedicated.md`.

| ID | Tarefa | Estado | Arquivos principais | Verificação / pendência |
|---|---|---|---|---|
| L1 | Separar Plan/Apply por branch, GitHub Environment, conta e state | `VERIFIED` | `.github/workflows/pipeline.yml`, `infra/data.tf` | Testes estáticos, `actionlint` e `terraform validate` aprovados; nenhuma chamada AWS executada. |
| L2 | Preservar os guards contra Destroy/Replace e bloquear deploy em PR/feature | `VERIFIED` | `.github/workflows/pipeline.yml`, `scripts/test_review_lambda_plan.py`, `scripts/test_pipeline_resource_discovery.py` | Testes de scripts aprovados; Plan/Apply limitados a `develop`/`main`, com Required reviewers. |
| L3 | Documentar ambientes, States, credenciais e JWT | `VERIFIED` | `README.md`, `docs/variables-and-secrets.md` | Documentação revisada em pt-BR; nenhum valor secreto, ID ou ARN de conta incluído. |
| L4 | Verificar autenticação, pacote e configuração Terraform sem AWS | `VERIFIED` | `test_handler.py`, `test_http_api.py`, `infra/test_function_url.py`, `infra/` | 19 testes da Lambda, 33 testes de scripts, 4 testes de configuração, `build.sh`, `pip-audit`, `terraform fmt -check`, `terraform validate` e `actionlint` aprovados. |
| L5 | Revisar diff/segredos, commitar, publicar branch e abrir PR | `IN_PROGRESS` | Worktree `feat/production-dedicated` | Próximo: inspeção final, commits convencionais, push e PR para `develop`; nenhum merge ou deploy. |

## Configuração externa pendente

- Criar/restringir Environments `homolog` (`develop`) e `production` (`main`) e configurar Required reviewers efetivos.
- Proteger a branch `main` com Pull Request obrigatório, checks requeridos e sem push direto.
- Cadastrar Variables e Secrets próprios por Environment conforme `docs/variables-and-secrets.md`; não reutilizar credenciais entre ambientes.
- Garantir buckets pertencentes à conta indicada por `AWS_EXPECTED_ACCOUNT_ID` e states VPC/EKS e RDS nos caminhos do ambiente correspondente.
- Validar permissões e disponibilidade de roles/recursos na conta destino antes de qualquer execução futura do pipeline.

Essas etapas são configuração operacional externa. Nesta implementação não foram feitas consultas AWS, Terraform Plan/Apply/Destroy ou deploy.
