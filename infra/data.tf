data "terraform_remote_state" "infra" {
  backend = "s3"

  config = {
    bucket                = var.terraform_state_bucket
    key                   = var.infra_state_key
    region                = var.region
    profile               = var.aws_profile
    expected_bucket_owner = var.aws_allowed_account_ids[0]
  }
}

data "terraform_remote_state" "db" {
  backend = "s3"

  config = {
    bucket                = var.terraform_state_bucket
    key                   = var.rds_state_key
    region                = var.region
    profile               = var.aws_profile
    expected_bucket_owner = var.aws_allowed_account_ids[0]
  }
}
