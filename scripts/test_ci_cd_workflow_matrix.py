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

    def test_opt_in_push_plan_and_explicit_manual_apply_keep_branch_mapping_and_gates(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        triggers = content.split("permissions:", 1)[0]
        gate = section(content, "gate", "checks")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        self.assertIn("on:\n  workflow_dispatch:", triggers)
        self.assertIn("  push:\n    branches: [develop, main]", triggers)
        self.assertNotIn("  pull_request:", triggers)
        self.assertIn("python scripts/validate_cd_trigger.py", gate)
        self.assertIn("AUTO_CD_ENABLED_HOMOLOG: ${{ vars.AUTO_CD_ENABLED_HOMOLOG }}", gate)
        self.assertIn("AUTO_CD_ENABLED_PRODUCTION: ${{ vars.AUTO_CD_ENABLED_PRODUCTION }}", gate)
        self.assertNotIn("configure-aws-credentials", gate)
        for job in (plan, apply):
            self.assertIn("github.ref == 'refs/heads/develop'", job)
            self.assertIn("github.ref == 'refs/heads/main'", job)
            self.assertIn("github.ref_protected", job)
            self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
            self.assertIn("TF_STATE_KEY: ${{ vars.AWS_TF_STATE_KEY }}", job)
            self.assertIn("TF_VAR_infra_state_key: ${{ vars.AWS_INFRA_STATE_KEY }}", job)
            self.assertIn("TF_VAR_rds_state_key: ${{ vars.AWS_RDS_STATE_KEY }}", job)
            self.assertIn("environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'homolog' }}", job)
        self.assertIn("github.event_name == 'workflow_dispatch'", plan)
        self.assertIn("needs.gate.outputs.auto_cd_enabled == 'true'", plan)
        self.assertIn("needs: [gate, checks]", plan)
        self.assertIn("github.event_name == 'workflow_dispatch'", apply)
        self.assertIn("inputs.apply == true", apply)
        self.assertIn("needs: [gate, plan]", apply)
        self.assertIn("TERRAFORM_APPLY_APPROVAL_CONFIGURED", apply)
        self.assertIn('test "$TERRAFORM_APPLY_APPROVAL_CONFIGURED" = true', apply)
        self.assertNotIn("github.event_name == 'push'", apply)

    def test_plan_and_apply_validate_injected_values_without_environment_admin_api(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        variables = (
            "AWS_REGION",
            "AWS_EXPECTED_ACCOUNT_ID",
            "AWS_TERRAFORM_STATE_BUCKET",
            "AWS_TF_STATE_KEY",
            "AWS_INFRA_STATE_KEY",
            "AWS_RDS_STATE_KEY",
            "AWS_LAMBDA_EXECUTION_ROLE_ARN",
            "TERRAFORM_APPLY_APPROVAL_CONFIGURED",
        )
        secrets = (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "DATABASE_USERNAME",
            "DATABASE_PASSWORD",
            "JWT_SECRET",
            "TF_PLAN_ENCRYPTION_KEY",
        )

        for job in (plan, apply):
            with self.subTest(job="plan" if job == plan else "apply"):
                self.assertNotIn("gh api", job)
                self.assertNotIn("/environments/", job)
                self.assertNotIn("REVIEWERS=", job)
                step_name = (
                    "Validar valores injetados pelo Environment"
                    if job == plan
                    else "Validar valores do Environment e sinalização de aprovação"
                )
                step = job.split(step_name, 1)[1].split("\n      - ", 1)[0]
                self.assertIn('[[ -n "${!name}" ]] ||', step)
                for name in variables:
                    self.assertIn(f"{name}: ${{{{ vars.{name} }}}}", step)
                for name in secrets:
                    self.assertIn(f"{name}: ${{{{ secrets.{name} }}}}", step)
                    self.assertNotRegex(step, rf"(?m)^\s*(?:echo|printf)\b[^\n]*\${name}\b")

    def test_lambda_plan_artifact_remains_encrypted_and_bound_to_run_and_commit(self):
        content = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
        plan = section(content, "plan", "apply")
        apply = section(content, "apply")
        for marker in ("lambda.tfplan.gpg", "lambda.tfplan.sha256", "lambda-plan-metadata.json", "lambda-deployment-config.sha256"):
            self.assertIn(marker, plan)
            self.assertIn(marker, apply)
        self.assertIn('"run_id":os.environ["GITHUB_RUN_ID"]', plan)
        self.assertIn('"run_attempt":os.environ["GITHUB_RUN_ATTEMPT"]', plan)
        self.assertIn('"commit":os.environ["DEPLOY_SHA"]', plan)
        self.assertIn("lambda_package_s3.py verify", apply)
        self.assertIn("python scripts/validate_lambda_state_keys.py", apply)
        self.assertNotRegex(content, r"(?<!\d)\d{12}(?!\d)")


if __name__ == "__main__":
    unittest.main()
