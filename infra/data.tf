data "terraform_remote_state" "infra" {
  backend = "s3"

  config = {
    bucket  = var.terraform_state_bucket
    key     = var.infra_state_key
    region  = var.region
    profile = var.aws_profile
  }
}

data "terraform_remote_state" "db" {
  backend = "s3"

  config = {
    bucket  = var.terraform_state_bucket
    key     = var.rds_state_key
    region  = var.region
    profile = var.aws_profile
  }
}
