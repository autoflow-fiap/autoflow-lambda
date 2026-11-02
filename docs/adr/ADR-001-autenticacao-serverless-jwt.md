# ADR-001 — Autenticação serverless e emissão de JWT

- **Status:** registrada a partir do código e da configuração atuais; aprovação histórica não localizada.
- **Data:** 02/11/2026.
- **Escopo:** autenticação de credenciais e emissão de token pela Lambda; a API Gateway e sua rota pertencem ao root `autoflow-infra`.

## Contexto

O AutoFlow autentica usuários com CPF/CNPJ e senha, armazena credenciais no PostgreSQL e protege operações de negócio no backend Spring Boot. A implementação observada usa uma função Python 3.12, invocada pela HTTP API via integração nativa `AWS_PROXY`, que consulta o RDS PostgreSQL e emite JWT HS256. O backend valida o token e continua responsável pela autorização de domínio.

As forças em oposição são separar a autenticação do backend e permitir login por um fluxo serverless versus duplicar uma fronteira de segurança, distribuir o segredo compartilhado, abrir conexão com o banco em execução Lambda e coordenar compatibilidade de claims entre emissores/validadores. Não foi localizado registro formal da decisão original nem comparação de custo ou latência; esta ADR formaliza a arquitetura refletida em código/configuração, não atribui aprovação histórica.

O root Lambda declara Python 3.12, timeout de 15 segundos, memória de 256 MB e execução na VPC, com acesso ao RDS. A função lê DB username/password e `JWT_SECRET` de variáveis de ambiente geradas pelo Terraform. As variáveis sensíveis são mascaradas em certas saídas do Terraform, mas seus valores necessários à configuração podem permanecer no Terraform State.

## Decisão

Manter a Lambda de autenticação como endpoint de login serverless, invocada pelo API Gateway HTTP API v2 de `autoflow-infra` usando `POST /auth/login`, `AWS_PROXY` e payload format `2.0`. A Lambda é responsável por:

1. interpretar JSON e normalizar CPF/CNPJ;
2. validar formato e dígitos verificadores;
3. consultar usuário e status do cliente no PostgreSQL;
4. comparar a senha com o hash BCrypt armazenado;
5. exigir cliente ativo para o papel `CLIENTE`;
6. emitir token assinado HS256, com `sub`, `role`, `iat`, `exp` e `email` quando disponível.

O prazo padrão do JWT é 3600 segundos, configurável por `JWT_EXPIRES_IN_SECONDS`. O secret HS256 é compartilhado com o backend, que verifica assinatura e expiração, recarrega o usuário/perfil/estado e aplica as regras Spring/domínio. O API Gateway atual não tem JWT authorizer nem substitui essa validação. O root deste repositório não deve ser tratado como proprietário das rotas ou permissões do API Gateway.

## Alternativas consideradas

Análise retrospectiva das opções tecnicamente plausíveis; não há prova de comparação formal, benchmark ou avaliação de custo.

| Alternativa | Mecanismo e benefícios possíveis | Trade-offs | Razão para não adotar como fluxo observado |
|---|---|---|---|
| Lambda de login + JWT HS256 (configuração atual) | Autenticação em função isolada, leitura do status atual no RDS e contrato JWT já consumido pelo backend; integração `AWS_PROXY` encaminha o evento HTTP diretamente. | Requer rede/credenciais de banco na Lambda, distribuição de segredo simétrico para signatário e verificador e compatibilidade de token. Conexões são abertas por invocação no código atual. | É a implementação presente e mantém a integração entre Lambda e backend sem mudança de contrato. A justificativa histórica de escolha não foi localizada. |
| Login realizado somente pelo backend Spring | Menos um runtime de autenticação e um secret issuer; reutiliza a conexão, segurança e tratamento de erros do backend. | Acopla login ao ciclo de disponibilidade/deploy do backend e abandona a rota serverless atual; exigiria alterar a entrada e o consumidor se mantido o contrato vigente. | Não é o caminho de login configurado no API Gateway atual. |
| Amazon Cognito ou IdP externo | Delegaria armazenamento de credenciais, emissão/rotação de tokens e fluxos de identidade ao provedor, conforme integração adotada. | Exigiria provisionar/conciliar usuários e senhas existentes, mapear CPF/CNPJ e perfis, ajustar o frontend/backend e validar custos e políticas. Não há integração ou plano de migração versionado. | Não há recurso/configuração de IdP ou necessidade documentada que justifique migrar a base de credenciais nesta decisão. |
| JWT Authorizer nativo do HTTP API | Pode validar tokens no Gateway usando configuração de issuer/JWKS e claims, rejeitando token antes da integração backend. | O token atual usa HS256, não declara `iss`/`aud` e depende de segredo compartilhado; adoção direta exigiria compatibilidade de algoritmo/claims e mudança coordenada. O authorizer não consulta estado/perfil no RDS. | Não está configurado; backend permanece responsável pela validação e autorização. Uma migração de token é decisão futura independente. |
| Lambda Authorizer para HS256 | Poderia validar no Gateway o token simétrico atual e barrar chamadas inválidas antes do backend. | Adiciona função, permissão, custo/latência de invocação/cache e gestão do segredo; duplica validação criptográfica, mas não substitui autorização e consulta de estado no backend. | Não há authorizer declarado no root API Gateway. Sua adoção requer decisão e operação próprias, não deve ser inferida da Lambda de login. |

## Consequências positivas

- O endpoint de login está isolado do backend e pode consultar credenciais/status persistidos antes de emitir token.
- BCrypt é usado para comparar a senha com o hash persistido, em vez de comparar texto simples.
- O backend recarrega usuário/perfil/estado e mantém a decisão final de acesso a operações de negócio.
- A permissão de invocação da função é declarada no root do API Gateway com escopo de rota; a Function URL não integra o fluxo documentado.
- Testes unitários cobrem validação de documento, corpo, consulta mockada, geração/validação do token e classes de resposta.

## Consequências negativas e riscos conhecidos

- Lambda e backend compartilham um segredo HS256; vazamento do segredo afeta tanto emissão quanto validação e rotação exige coordenação.
- O `sub` contém CPF/CNPJ normalizado e o token pode incluir email. JWT é assinado, não criptografado; quem obtiver o token pode ler claims até sua expiração.
- Não foi encontrada revogação explícita de JWT. O backend recarrega o usuário e status, mas não há mecanismo de revogação por token descrito; um token válido pode permanecer utilizável até expirar se as regras de domínio ainda permitirem.
- `handler.py` abre e fecha uma conexão PostgreSQL em cada busca/autenticação. Não há pool compartilhado nem RDS Proxy declarado; concorrência pode elevar conexões e latência no banco.
- Credenciais de banco e secret JWT são variáveis de ambiente da Lambda declaradas via Terraform. `sensitive` não elimina os valores do State; acesso ao State/Plan e às APIs de configuração da função deve ser restrito.
- Timeout de conexão ao PostgreSQL é cinco segundos dentro do timeout de 15 segundos da função; falhas de DB retornam erro 500 e não há retry de aplicação declarado.
- A validade padrão de uma hora limita a janela do token, mas não é revogação; não há benchmark ou SLO de autenticação registrado.

## Riscos e mitigação

| Risco | Controle observado ou melhoria futura |
|---|---|
| Tentativa de login com documento ou senha inválidos | Respostas 400/401 conforme entrada; API Gateway declara throttling da rota. A eficácia operacional do limite não foi verificada na AWS. |
| Exposição de CPF/CNPJ, email, senha ou token em logs | O handler imprime tipo de exceção, sem mensagem/credencial; manter access logs sem body/headers sensíveis e verificar telemetria ponta a ponta antes de uso real. |
| Comprometimento do segredo HS256 | Restringir Secrets, State, Plan e permissões de leitura da configuração Lambda; planejar rotação coordenada. Avaliar futuramente assinatura assimétrica/JWKS e claims `iss`/`aud`. |
| Claims pessoais em token | Minimizar claims em mudança compatível; atualmente o `sub` é CPF/CNPJ e pode haver email. Avaliar subject opaco em migração coordenada, sem alterar o contrato nesta tarefa. |
| Token sem revogação imediata | Manter validação do estado atual de usuário/cliente no backend e expiração limitada; avaliar `jti`/lista de revogação ou tokens curtos apenas com desenho de armazenamento, consistência e custo. |
| Exaustão de conexões PostgreSQL sob concorrência | Medir conexões/latência em ambiente autorizado e avaliar RDS Proxy ou reuso/pooling compatível com Lambda em trabalho futuro. Nada disso está configurado nesta decisão. |
| Estado do banco inconsistente com cliente | Consultar status na autenticação e novamente no backend; testes devem cobrir cliente inativo e mudança de status após emissão de token. |

## Referências

- [RFC-001 — Autenticação serverless e JWT](../rfc/RFC-001-autenticacao-serverless-jwt.md)
- [README da Lambda](../../README.md)
- [Handler de autenticação](../../handler.py) e [testes do handler](../../test_handler.py)
- [Terraform da função](../../infra/lambda.tf), [variáveis](../../infra/variables.tf) e [backend State](../../infra/backend.tf)
- [Contrato API Gateway e separação de ownership](../api-gateway.md)
- [Arquitetura atual do API Gateway](https://github.com/autoflow-fiap/autoflow-infra/blob/develop/docs/api-gateway/arquitetura.md)
- [Validação JWT e autorização no backend](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/src/main/java/com/autoflow/infrastructure/security/JwtFilter.java)
- [Variáveis e Secrets](../variables-and-secrets.md)
