# Integração Lambda com Amazon API Gateway

O repositório `autoflow-infra` configura Amazon API Gateway HTTP API v2 para encaminhar `POST /auth/login` à Lambda pela integração nativa `AWS_PROXY`, payload `2.0`. A permissão `lambda:InvokeFunction` é restrita à conta e à rota de login. A Function URL não faz parte do fluxo configurado.

O Terraform deste repositório provisiona a função Python 3.12 em subnets privadas, com acesso ao RDS PostgreSQL. Após autenticação, o backend Spring Boot valida o JWT nas rotas protegidas. O contrato de API e exemplos de requisição permanecem no [guia OpenAPI](https://github.com/autoflow-fiap/autoflow/blob/develop/docs/openapi/README.md) e na [coleção Postman](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/postman/autoflow-serverless-auth.postman_collection.json).

## Provisionamento após reset

Após reset do AWS Academy Learner Lab, reexecute as pipelines CI/CD dos repositórios na ordem de dependências para provisionar novamente VPC/EKS, RDS, Lambda, API Gateway e aplicação.
