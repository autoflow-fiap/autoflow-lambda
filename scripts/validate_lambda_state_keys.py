"""Valida o prefixo e a unicidade das keys Terraform consumidas pela Lambda."""

from __future__ import annotations

import os
import sys

ENVIRONMENTS = {"homolog", "production"}
KEY_VARIABLES = (
    "TF_STATE_KEY",
    "TF_VAR_infra_state_key",
    "TF_VAR_rds_state_key",
)


def validate_state_keys(environment: str | None, keys: tuple[str | None, ...]) -> None:
    if environment not in ENVIRONMENTS:
        raise ValueError("Environment GitHub inválido para as keys Terraform da Lambda.")
    if not keys:
        raise ValueError("Informe ao menos uma key Terraform para validar.")

    prefix = f"{environment}/"
    for key in keys:
        if not isinstance(key, str) or not key or key != key.strip():
            raise ValueError("Todas as keys Terraform devem estar configuradas sem espaços externos.")
        if not key.startswith(prefix) or not key[len(prefix) :]:
            raise ValueError("Cada key Terraform deve estar no prefixo do Environment selecionado.")
        if any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("As keys Terraform devem ter segmentos de caminho válidos.")

    if len(set(keys)) != len(keys):
        raise ValueError("As keys da Lambda, VPC/EKS e RDS devem ser distintas.")


def main() -> int:
    try:
        validate_state_keys(
            os.environ.get("GITHUB_DEPLOYMENT_ENVIRONMENT"),
            tuple(os.environ.get(name) for name in KEY_VARIABLES),
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Keys Terraform validadas para o Environment e distintas entre os roots consumidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
