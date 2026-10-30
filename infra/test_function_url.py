import pathlib
import unittest


ROOT = pathlib.Path(__file__).parent


class FunctionUrlConfigurationTest(unittest.TestCase):
    def test_url_resource_and_public_modes_are_removed_from_configuration(self):
        variables = (ROOT / "variables.tf").read_text(encoding="utf-8")
        lambda_tf = (ROOT / "lambda.tf").read_text(encoding="utf-8")
        self.assertNotIn('variable "enable_lambda_function_url"', variables)
        self.assertNotIn("enable_academic_demo_function_url", variables)
        self.assertNotIn("academic_demo_environment_confirmed", variables)
        self.assertNotIn('resource "aws_lambda_function_url"', lambda_tf)
        self.assertNotIn('authorization_type = "NONE"', lambda_tf)

    def test_no_function_url_permissions_are_declared(self):
        lambda_tf = (ROOT / "lambda.tf").read_text(encoding="utf-8")
        self.assertNotIn('resource "aws_lambda_permission"', lambda_tf)
        self.assertNotIn('principal              = "*"', lambda_tf)

    def test_lambda_runtime_and_network_configuration_are_unchanged(self):
        lambda_tf = (ROOT / "lambda.tf").read_text(encoding="utf-8")
        function = lambda_tf.split('resource "aws_lambda_function" "cpf_validator" {', 1)[1].split("\n}", 1)[0]
        self.assertRegex(function, r'(?m)^\s*runtime\s+= "python3\.12"$')
        self.assertRegex(function, r"(?m)^\s*timeout\s+= 15$")
        self.assertRegex(function, r"(?m)^\s*memory_size\s+= 256$")
        self.assertIn("vpc_config", function)
        self.assertIn('data.terraform_remote_state.db.outputs.lambda_security_group_id', function)

    def test_lambda_root_has_no_api_gateway_or_static_aws_keys(self):
        files = [path.read_text(encoding="utf-8") for path in ROOT.glob("*.tf")]
        source = "\n".join(files)
        self.assertNotIn("aws_apigatewayv2_", source)
        self.assertNotIn("aws_access_key_id", source)
        self.assertNotIn("aws_secret_access_key", source)


if __name__ == "__main__":
    unittest.main()
