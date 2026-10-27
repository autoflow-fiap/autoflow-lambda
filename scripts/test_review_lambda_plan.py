import unittest
from pathlib import Path

from review_lambda_plan import review_plan


def change(address, actions, before=None, after=None):
    return {"address": address, "change": {"actions": actions, "before": before, "after": after}}


class ReviewLambdaPlanTests(unittest.TestCase):
    def test_manual_dispatch_runs_plan_and_approved_apply_on_develop(self):
        workflow = (Path(__file__).parents[1] / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        condition = "github.ref == 'refs/heads/develop' && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
        plan, apply = workflow.split("  plan:", 1)[1].split("  apply:", 1)[0], workflow.split("  apply:", 1)[1]
        self.assertIn(condition, plan)
        self.assertIn(condition, apply)
        self.assertIn("environment: homolog", apply)
        self.assertIn("required_reviewers", apply)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", apply)
        self.assertNotIn("vars.AWS_LAMBDA_FUNCTION_NAME", workflow)
        self.assertEqual(workflow.count("AWS_LAMBDA_FUNCTION_NAME: autoflow-cpf-validator-homolog"), 2)

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
