from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def section(content: str, job: str, next_job: str | None = None) -> str:
    start = content.index(f"\n  {job}:\n") + 1
    end = content.index(f"\n  {next_job}:\n", start) if next_job else len(content)
    return content[start:end]


class CiCdWorkflowMatrixTests(unittest.TestCase):
    def test_ci_triggers_are_automatic_and_do_not_access_aws(self):
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        triggers = ci.split("permissions:", 1)[0]
        self.assertIn("branches: [develop, main, 'feature/**']", triggers)
        self.assertIn("branches: [develop, main]", triggers)
        self.assertNotIn("workflow_dispatch:", triggers)
        self.assertNotRegex(ci, r"(?im)^\s*run:.*\bterraform\s+(?:plan|apply|destroy)\b")
        self.assertNotIn("aws-actions/configure-aws-credentials", ci)

    def test_plan_only_dispatch_and_explicit_apply_keep_branch_mapping_and_gates(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        triggers = content.split("permissions:", 1)[0]
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        self.assertIn("on:\n  workflow_dispatch:", triggers)
        self.assertNotIn("  push:", triggers)
        self.assertNotIn("  pull_request:", triggers)
        for job in (plan, apply):
            self.assertIn("refs/heads/develop", job)
            self.assertIn("refs/heads/main", job)
            self.assertIn("github.ref_protected", job)
            self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", job)
            self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", job)
            self.assertIn("TF_VAR_rds_state_key: ${{ vars.AWS_RDS_STATE_KEY }}", job)
        self.assertIn("github.event_name == 'workflow_dispatch'", plan)
        self.assertNotIn('test "$APPROVAL_CONFIGURED" = true', plan)
        self.assertIn("required_reviewers", plan)
        self.assertIn("github.event_name == 'workflow_dispatch'", apply)
        self.assertIn("inputs.apply == true", apply)
        self.assertIn("needs: plan", apply)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", apply)
        self.assertIn("required_reviewers", apply)
        self.assertIn('test "$APPROVAL_CONFIGURED" = true', apply)
        self.assertNotIn("github.event_name == 'push'", plan + apply)

    def test_lambda_plan_artifact_remains_encrypted_and_bound_to_run_and_commit(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        for marker in ("lambda.tfplan.gpg", "lambda.tfplan.sha256", "lambda-plan-metadata.json", "lambda-deployment-config.sha256"):
            self.assertIn(marker, plan)
            self.assertIn(marker, apply)
        self.assertIn('"run_id":os.environ["GITHUB_RUN_ID"]', plan)
        self.assertIn('"run_attempt":os.environ["GITHUB_RUN_ATTEMPT"]', plan)
        self.assertIn('"commit":os.environ["GITHUB_SHA"]', plan)
        self.assertIn("lambda_package_s3.py verify", apply)
        self.assertIn("python scripts/validate_lambda_state_keys.py", apply)
        self.assertNotRegex(content, r"(?<!\d)\d{12}(?!\d)")


if __name__ == "__main__":
    unittest.main()
