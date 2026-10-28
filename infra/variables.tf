variable "region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  description = "Perfil AWS opcional fornecido pela configuração local do processo."
  type        = string
  default     = null
}

variable "aws_allowed_account_ids" {
  description = "Contas AWS permitidas para este provider; fornecidas externamente por ambiente."
  type        = list(string)

  validation {
    condition     = length(var.aws_allowed_account_ids) > 0 && alltrue([for id in var.aws_allowed_account_ids : can(regex("^[0-9]{12}$", id))])
    error_message = "aws_allowed_account_ids deve conter pelo menos um ID de conta AWS válido, fornecido externamente."
  }
}

variable "environment" {
  type        = string
  description = "Ambiente que receberá os recursos da autenticação."
  default     = "homolog"

  validation {
    condition     = contains(["homolog", "production"], var.environment)
    error_message = "environment deve ser homolog ou production."
  }
}

variable "lambda_name" {
  type    = string
  default = "autoflow-cpf-validator"
}

variable "db_name" {
  type    = string
  default = "autoflow_db"
}

variable "db_username" {
  type      = string
  sensitive = true
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  sensitive = true

  validation {
    condition     = length(trimspace(var.jwt_secret)) >= 32
    error_message = "jwt_secret deve possuir pelo menos 32 caracteres."
  }
}

variable "jwt_expires_in_seconds" {
  type    = number
  default = 3600

  validation {
    condition     = var.jwt_expires_in_seconds > 0
    error_message = "jwt_expires_in_seconds deve ser maior que zero."
  }
}

variable "role_arn" {
  description = "Role de execução Lambda aprovada para o ambiente selecionado."
  type        = string
  default     = null
}

variable "terraform_state_bucket" {
  description = "Bucket que contém os states Terraform consumidos pela Lambda."
  type        = string
}

variable "infra_state_key" {
  description = "Key do state de VPC/EKS consumido pela Lambda."
  type        = string
  default     = "infra/terraform.tfstate"
}

variable "rds_state_key" {
  description = "Key do state RDS consumido pela Lambda."
  type        = string
  default     = "rds/terraform.tfstate"
}

variable "lambda_package_bucket" {
  description = "Bucket S3 existente que armazena os pacotes imutáveis da Lambda."
  type        = string

  validation {
    condition     = length(trimspace(var.lambda_package_bucket)) > 0
    error_message = "lambda_package_bucket deve identificar um bucket S3 existente."
  }
}

variable "lambda_package_key" {
  description = "Chave S3 isolada do pacote, contendo o SHA-256 hexadecimal no nome."
  type        = string

  validation {
    condition     = can(regex("^lambda-packages/sha256/[0-9a-f]{64}\\.zip$", var.lambda_package_key))
    error_message = "lambda_package_key deve usar lambda-packages/sha256/<sha256-hex>.zip."
  }
}

variable "lambda_package_source_code_hash" {
  description = "SHA-256 binário do pacote, codificado em Base64 como exige o AWS provider."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9+/]{43}=$", var.lambda_package_source_code_hash))
    error_message = "lambda_package_source_code_hash deve ser um SHA-256 válido em Base64."
  }
}

variable "lambda_package_version" {
  description = "VersionId do objeto S3 publicado e aprovado no Plan."
  type        = string

  validation {
    condition     = length(trimspace(var.lambda_package_version)) > 0 && var.lambda_package_version != "null"
    error_message = "lambda_package_version deve ser um VersionId S3 não nulo."
  }
}
