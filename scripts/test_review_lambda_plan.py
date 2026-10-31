import unittest
from pathlib import Path

from review_lambda_plan import review_plan


def change(address, actions, before=None, after=None):
    return {"address": address, "change": {"actions": actions, "before": before, "after": after}}


class ReviewLambdaPlanTests(unittest.TestCase):
    def test_develop_routes_to_homolog_and_main_routes_to_production(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        conditions = {
            "plan": "(github.ref == 'refs/heads/develop' || github.ref == 'refs/heads/main') && github.event_name == 'workflow_dispatch'",
            "apply": "(github.ref == 'refs/heads/develop' || github.ref == 'refs/heads/main') && github.event_name == 'workflow_dispatch' && inputs.apply == true",
        }
        plan, apply = workflow.split("  plan:", 1)[1].split("\n  apply:\n", 1)[0], workflow.split("\n  apply:\n", 1)[1]
        self.assertIn(conditions["plan"], plan)
        self.assertIn(conditions["apply"], apply)
        for job in (plan, apply):
            self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("autoflow-cpf-validator-${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("TF_VAR_environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("required_reviewers", job)
            self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", job)
        self.assertNotIn("vars.AWS_LAMBDA_FUNCTION_NAME", workflow)

    def test_state_keys_are_validated_and_fingerprint_is_rechecked_before_apply(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        plan = workflow.split("  plan:", 1)[1].split("  apply:", 1)[0]
        apply = workflow.split("\n  apply:\n", 1)[1]
        self.assertIn("GITHUB_DEPLOYMENT_ENVIRONMENT", plan)
        self.assertIn("GITHUB_DEPLOYMENT_ENVIRONMENT", apply)
        self.assertIn("deployment_config_fingerprint: ${{ steps.deployment_config.outputs.fingerprint }}", plan)
        self.assertIn("PLAN_DEPLOYMENT_CONFIG_FINGERPRINT: ${{ needs.plan.outputs.deployment_config_fingerprint }}", apply)
        self.assertIn("python scripts/validate_lambda_state_keys.py", plan)
        self.assertIn("python scripts/validate_lambda_state_keys.py", apply)
        self.assertIn("Fingerprint do Environment e dos States selecionados", plan)
        self.assertIn("Revalidar fingerprint do Environment e dos States", apply)
        self.assertIn("lambda-deployment-config.sha256", workflow)
        self.assertLess(
            apply.index("Revalidar fingerprint do Environment e dos States"),
            apply.index("terraform init -input=false -reconfigure"),
        )
        self.assertLess(
            apply.index("CURRENT_DEPLOYMENT_CONFIG="),
            apply.index("aws-actions/configure-aws-credentials"),
        )
        self.assertIn('backend-config="allowed_account_ids=$TF_VAR_aws_allowed_account_ids"', workflow)
        self.assertIn('--expected-bucket-owner "$AWS_EXPECTED_ACCOUNT_ID"', workflow)
        self.assertNotIn("terraform.tfstate", workflow)

    def test_apply_requires_an_approved_environment_and_is_limited_to_deploy_branches(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        apply = workflow.split("\n  apply:\n", 1)[1]
        self.assertIn("required_reviewers", apply)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", apply)
        self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", apply)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.apply == true", apply)
        self.assertNotIn("github.event_name == 'push'", apply)
        self.assertNotIn("pull_request", apply)

    def test_plan_still_reviews_destroy_replacement_and_lambda_identity(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("python ../scripts/review_lambda_plan.py lambda-plan.json"), 2)
        from review_lambda_plan import IDENTITY_FIELDS

        self.assertEqual(IDENTITY_FIELDS, ("function_name", "package_type", "handler", "runtime"))

    def test_allows_plan_without_changes(self):
        self.assertEqual(review_plan({"resource_changes": []}), [])

    def test_allows_noop_and_regular_update_without_identity_change(self):
        plan = {"resource_changes": [
            change("aws_lambda_function.cpf_validator", ["update"], {"function_name": "autoflow-cpf-validator-homolog", "runtime": "python3.12"}, {"function_name": "autoflow-cpf-validator-homolog", "runtime": "python3.12"}),
            change("aws_security_group_rule.example", ["no-op"]),
        ]}
        self.assertEqual(review_plan(plan), [])

    def test_blocks_delete_and_replacement(self):
        for actions in (["delete"], ["delete", "create"], ["create", "delete"]):
            with self.subTest(actions=actions):
                findings = review_plan({"resource_changes": [change("aws_lambda_function.cpf_validator", actions)]})
                self.assertTrue(any("destrutiva/replacement" in item for item in findings))

    def test_blocks_lambda_identity_changes(self):
        for field in ("function_name", "package_type", "handler", "runtime"):
            with self.subTest(field=field):
                findings = review_plan({"resource_changes": [change(
                    "aws_lambda_function.cpf_validator", ["update"], {field: "anterior"}, {field: "novo"}
                )]})
                self.assertTrue(any(field in item and "identidade" in item for item in findings))

    def test_allows_initial_creation_when_function_is_absent(self):
        initial_function = {
            "function_name": "autoflow-cpf-validator-homolog",
            "package_type": "Zip",
            "handler": "handler.lambda_handler",
            "runtime": "python3.12",
        }
        self.assertEqual(review_plan({"resource_changes": [change(
            "aws_lambda_function.cpf_validator", ["create"], before=None, after=initial_function
        )]}), [])

    def test_allows_create_of_other_resource(self):
        self.assertEqual(review_plan({"resource_changes": [change("aws_iam_role.example", ["create"])]}), [])


if __name__ == "__main__":
    unittest.main()
