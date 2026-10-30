from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PipelineResourceDiscoveryTests(unittest.TestCase):
    def test_function_name_uses_terraform_default_for_both_environments(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertNotIn("vars.AWS_LAMBDA_FUNCTION_NAME", workflow)
        self.assertEqual(
            workflow.count(
                "AWS_LAMBDA_FUNCTION_NAME: autoflow-cpf-validator-${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}"
            ),
            2,
        )
        variables = (ROOT / "infra/variables.tf").read_text(encoding="utf-8")
        self.assertIn('variable "lambda_name"', variables)
        lambda_name = re.search(
            r'variable "lambda_name"\s*\{[^}]*default\s*=\s*"([^"]+)"', variables, re.DOTALL
        ).group(1)
        self.assertEqual(f"{lambda_name}-production", "autoflow-cpf-validator-production")
        lambda_tf = (ROOT / "infra/lambda.tf").read_text(encoding="utf-8")
        self.assertIn('function_name     = "${var.lambda_name}-${var.environment}"', lambda_tf)

    def test_package_bucket_reuses_the_validated_terraform_state_bucket(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertNotIn("vars.AWS_LAMBDA_PACKAGE_BUCKET", workflow)
        self.assertNotIn("AWS_LAMBDA_PACKAGE_BUCKET", workflow)
        self.assertIn('--bucket "$TF_STATE_BUCKET"', workflow)

    def test_jobs_bind_github_environment_for_credentials_variables_and_secrets(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        environment = "environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}"
        self.assertEqual(workflow.count(f"\n    {environment}"), 2)
        plan = workflow.split("  plan:", 1)[1].split("  apply:", 1)[0]
        apply = workflow.split("  apply:", 1)[1]
        for job in (plan, apply):
            self.assertIn(environment, job)
            for value in (
                "vars.AWS_EXPECTED_ACCOUNT_ID",
                "vars.AWS_TERRAFORM_STATE_BUCKET",
                "vars.AWS_TF_STATE_KEY",
                "vars.AWS_INFRA_STATE_KEY",
                "vars.AWS_RDS_STATE_KEY",
                "vars.AWS_LAMBDA_EXECUTION_ROLE_ARN",
                "secrets.AWS_ACCESS_KEY_ID",
                "secrets.AWS_SECRET_ACCESS_KEY",
                "secrets.AWS_SESSION_TOKEN",
                "secrets.DATABASE_USERNAME",
                "secrets.DATABASE_PASSWORD",
                "secrets.JWT_SECRET",
            ):
                self.assertIn(value, job)

    def test_expected_account_is_required_before_aws_operations_in_both_jobs(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        plan = workflow.split("  plan:", 1)[1].split("  apply:", 1)[0]
        apply = workflow.split("  apply:", 1)[1]
        for job in (plan, apply):
            self.assertIn('[[ "$AWS_EXPECTED_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]', job)
            self.assertIn('^arn:aws:iam::${AWS_EXPECTED_ACCOUNT_ID}:role/.+', job)
            self.assertIn("python scripts/verify_aws_account.py", job)
            self.assertIn("--expected-bucket-owner \"$AWS_EXPECTED_ACCOUNT_ID\"", job)
            self.assertIn('expected_bucket_owner=$AWS_EXPECTED_ACCOUNT_ID', job)
            self.assertLess(job.index('[[ "$AWS_EXPECTED_ACCOUNT_ID"'), job.index("aws-actions/configure-aws-credentials"))
            self.assertLess(job.index("python scripts/verify_aws_account.py"), job.index("aws ec2 describe-availability-zones"))

    def test_production_and_homolog_states_and_resources_are_distinct(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        for key in (
            "production/lambda/terraform.tfstate",
            "production/eks/terraform.tfstate",
            "production/rds/terraform.tfstate",
            "lambda/terraform.tfstate",
            "eks/terraform.tfstate",
            "rds/terraform.tfstate",
        ):
            self.assertIn(key, workflow)
        self.assertIn("'production' || 'homolog'", workflow)
        self.assertIn("TF_VAR_environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", workflow)
        data_tf = (ROOT / "infra/data.tf").read_text(encoding="utf-8")
        self.assertEqual(data_tf.count("expected_bucket_owner = var.aws_allowed_account_ids[0]"), 2)

    def test_feature_and_pull_request_events_cannot_run_aws_plan_or_apply(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        checks = workflow.split("  checks:", 1)[1].split("  plan:", 1)[0]
        deploy_condition = "(github.ref == 'refs/heads/develop' || github.ref == 'refs/heads/main') && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
        self.assertIn("branches: [develop, main]", workflow)
        self.assertIn("branches: [develop, main]", workflow.split("  pull_request:", 1)[1])
        self.assertEqual(workflow.count(deploy_condition), 2)
        self.assertNotIn("configure-aws-credentials", checks)
        self.assertNotRegex(checks, re.compile(r"\baws\s+(?:sts|s3|lambda|ec2)\b"))
        self.assertNotRegex(checks, re.compile(r"terraform\s+(?:plan|apply|destroy)\b"))
        automatic_pr = (ROOT / ".github/workflows/pr-automatico.yaml").read_text(encoding="utf-8")
        self.assertIn("- main", automatic_pr)
        self.assertIn("- feat/production-dedicated", automatic_pr)

    def test_workflow_and_terraform_do_not_pin_an_aws_account_id_or_arn(self):
        files = [
            ROOT / ".github/workflows/pipeline.yml",
            ROOT / "infra",
            ROOT / "README.md",
            ROOT / "docs/variables-and-secrets.md",
        ]
        contents = []
        for path in files:
            if path.is_dir():
                contents.extend(file.read_text(encoding="utf-8") for file in path.rglob("*.tf"))
            else:
                contents.append(path.read_text(encoding="utf-8"))
        for content in contents:
            self.assertIsNone(re.search(r"(?<!\d)\d{12}(?!\d)", content))
            self.assertNotRegex(content, r"arn:aws(?:-[a-z]+)?:[a-z0-9-]+::\d{12}:")


if __name__ == "__main__":
    unittest.main()
