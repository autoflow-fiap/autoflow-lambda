import unittest

from validate_lambda_state_keys import validate_state_keys


class ValidateLambdaStateKeysTests(unittest.TestCase):
    def test_accepts_distinct_external_keys_under_the_selected_environment(self):
        validate_state_keys(
            "homolog",
            (
                "homolog/root-a/state.tfstate",
                "homolog/root-b/state.tfstate",
                "homolog/root-c/state.tfstate",
            ),
        )
        validate_state_keys(
            "production",
            (
                "production/custom-lambda-key",
                "production/custom-infra-key",
                "production/custom-rds-key",
            ),
        )

    def test_rejects_unknown_environment(self):
        with self.assertRaisesRegex(ValueError, "Environment GitHub inválido"):
            validate_state_keys("staging", ("staging/a", "staging/b", "staging/c"))

    def test_rejects_missing_key(self):
        with self.assertRaisesRegex(ValueError, "Todas as keys"):
            validate_state_keys("homolog", ("homolog/a", None, "homolog/c"))

    def test_rejects_key_from_another_environment(self):
        with self.assertRaisesRegex(ValueError, "prefixo do Environment"):
            validate_state_keys("production", ("homolog/a", "production/b", "production/c"))

    def test_rejects_duplicate_keys_across_roots(self):
        with self.assertRaisesRegex(ValueError, "devem ser distintas"):
            validate_state_keys("homolog", ("homolog/same", "homolog/infra", "homolog/same"))

    def test_rejects_empty_or_traversal_path_segments(self):
        for key in ("homolog/", "homolog//state", "homolog/../state", "homolog/./state"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_state_keys("homolog", (key, "homolog/infra", "homolog/rds"))


if __name__ == "__main__":
    unittest.main()
