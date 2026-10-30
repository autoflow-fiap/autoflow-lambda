from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def remote_init_commands():
    commands = []
    workflows = list((ROOT / ".github/workflows").glob("*.yml"))
    workflows.extend((ROOT / ".github/workflows").glob("*.yaml"))
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        text = re.sub(r"\\\r?\n\s*", " ", text)
        for match in re.finditer(r"\bterraform(?:\s+-chdir=\S+)?\s+init\b([^\r\n]*)", text):
            command = match.group(0)
            if "-backend=false" not in command:
                commands.append((workflow.name, command))
    return commands


class TerraformBackendConfigTests(unittest.TestCase):
    def test_s3_backend_blocks_do_not_declare_unsupported_arguments(self):
        backend_files = []
        for terraform_file in (ROOT / "infra").rglob("*.tf"):
            text = terraform_file.read_text(encoding="utf-8")
            if re.search(r'backend\s+"s3"', text):
                backend_files.append(terraform_file)
                self.assertNotIn("expected_bucket_owner", text, str(terraform_file))
        self.assertEqual(backend_files, [ROOT / "infra/backend.tf"])

    def test_remote_init_uses_supported_account_restricted_s3_arguments(self):
        commands = remote_init_commands()
        self.assertTrue(commands, "Nenhum terraform init remoto foi encontrado nos workflows.")
        for workflow, command in commands:
            with self.subTest(workflow=workflow, command=command):
                self.assertNotIn("expected_bucket_owner", command)
                self.assertIn('backend-config="allowed_account_ids=$TF_VAR_aws_allowed_account_ids"', command)
                self.assertIn('backend-config="encrypt=true"', command)
                self.assertIn('backend-config="use_lockfile=true"', command)

    def test_remote_states_use_the_externally_supplied_account_allowlist(self):
        data = (ROOT / "infra/data.tf").read_text(encoding="utf-8")
        self.assertNotIn("expected_bucket_owner", data)
        self.assertEqual(data.count("allowed_account_ids = var.aws_allowed_account_ids"), 2)
        variables = (ROOT / "infra/variables.tf").read_text(encoding="utf-8")
        allowlist = variables.split('variable "aws_allowed_account_ids"', 1)[1].split("}", 1)[0]
        self.assertNotIn("default", allowlist)
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertIn('TF_VAR_aws_allowed_account_ids: \'["${{ vars.AWS_EXPECTED_ACCOUNT_ID }}"]\'', workflow)

    def test_homolog_uses_its_external_keys_and_does_not_run_a_production_deploy(self):
        workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
        self.assertIn("environment: homolog", workflow)
        self.assertIn("TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", workflow)
        self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", workflow)
        self.assertIn("TF_VAR_rds_state_key: ${{ vars.AWS_RDS_STATE_KEY }}", workflow)
        self.assertIn("github.ref == 'refs/heads/develop'", workflow)


if __name__ == "__main__":
    unittest.main()
