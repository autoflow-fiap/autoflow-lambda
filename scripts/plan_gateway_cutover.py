"""Planeja o fechamento da URL IAM usando a configuração atual, sem expor segredos.

Somente leitura AWS e terraform plan. O pacote lambda.zip existente deve ser
revisado; qualquer alteração de código fora do cutover deve ser rejeitada.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

from validate_lambda_state_keys import validate_state_keys


def query(*args):
    result = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Consulta AWS falhou; revise perfil, sessão e permissões")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--function", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--infra-state-key", required=True)
    parser.add_argument("--rds-state-key", required=True)
    args = parser.parse_args()
    validate_state_keys("homolog", (args.infra_state_key, args.rds_state_key))
    if query("sts", "get-caller-identity")["Account"] != args.account:
        raise RuntimeError("Conta AWS diferente da aprovada")
    configuration = query("lambda", "get-function-configuration", "--function-name", args.function, "--region", args.region)
    package_path = Path(__file__).resolve().parents[1] / "lambda.zip"
    local_hash = base64.b64encode(hashlib.sha256(package_path.read_bytes()).digest()).decode()
    if local_hash != configuration["CodeSha256"]:
        raise RuntimeError("lambda.zip diverge do pacote implantado; fechamento abortado para evitar atualização de código")
    values = configuration["Environment"]["Variables"]
    environment = values.get("AUTOFLOW_ENVIRONMENT", "homolog")
    if environment != "homolog" or not args.function.endswith("-homolog"):
        raise RuntimeError("Este procedimento é exclusivo de homologação")
    env = dict(os.environ)
    variables = {
        "aws_allowed_account_ids": json.dumps([args.account]),
        "region": args.region, "role_arn": configuration["Role"],
        "environment": environment, "lambda_name": args.function.removesuffix("-homolog"),
        "terraform_state_bucket": args.bucket,
        "infra_state_key": args.infra_state_key, "rds_state_key": args.rds_state_key,
        "db_name": values["DB_NAME"], "db_username": values["DB_USERNAME"],
        "db_password": values["DB_PASSWORD"], "jwt_secret": values["JWT_SECRET"],
        "jwt_expires_in_seconds": values.get("JWT_EXPIRES_IN_SECONDS", "3600"),
    }
    env.update({"TF_VAR_" + key: value for key, value in variables.items()})
    subprocess.run(["terraform", "plan", "-input=false", "-lock-timeout=60s", "-no-color", "-out=function-url-close-minimal.tfplan"],
                   cwd=Path(__file__).resolve().parents[1] / "infra", env=env, check=True)


if __name__ == "__main__":
    main()
