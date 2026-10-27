from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PipelineResourceDiscoveryTests(unittest.TestCase):
    def test_function_name_uses_terraform_default_without_github_variable(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertNotIn("vars.AWS_LAMBDA_FUNCTION_NAME", workflow)
        self.assertEqual(workflow.count("AWS_LAMBDA_FUNCTION_NAME: autoflow-cpf-validator-homolog"), 2)
        self.assertIn('variable "lambda_name"', (ROOT / "infra/variables.tf").read_text(encoding="utf-8"))

    def test_package_bucket_reuses_the_validated_terraform_state_bucket(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertNotIn("vars.AWS_LAMBDA_PACKAGE_BUCKET", workflow)
        self.assertNotIn("AWS_LAMBDA_PACKAGE_BUCKET", workflow)
        self.assertIn('--bucket "$TF_STATE_BUCKET"', workflow)


if __name__ == "__main__":
    unittest.main()
