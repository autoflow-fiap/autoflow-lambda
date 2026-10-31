resource "aws_lambda_function" "cpf_validator" {
  function_name     = "${var.lambda_name}-${var.environment}"
  role              = var.role_arn
  handler           = "handler.lambda_handler"
  runtime           = "python3.12"
  s3_bucket         = var.lambda_package_bucket
  s3_key            = var.lambda_package_key
  s3_object_version = var.lambda_package_version
  source_code_hash  = var.lambda_package_source_code_hash
  timeout           = 15
  memory_size       = 256

  vpc_config {
    subnet_ids = data.terraform_remote_state.infra.outputs.private_subnet_ids

    security_group_ids = [
      data.terraform_remote_state.db.outputs.lambda_security_group_id
    ]
  }

  environment {
    variables = {
      AUTOFLOW_ENVIRONMENT   = var.environment
      DB_HOST                = data.terraform_remote_state.db.outputs.postgres_endpoint
      DB_PORT                = tostring(data.terraform_remote_state.db.outputs.postgres_port)
      DB_NAME                = var.db_name
      DB_USERNAME            = var.db_username
      DB_PASSWORD            = var.db_password
      JWT_SECRET             = var.jwt_secret
      JWT_EXPIRES_IN_SECONDS = tostring(var.jwt_expires_in_seconds)
    }
  }
}
