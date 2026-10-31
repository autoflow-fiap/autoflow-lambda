"""Bloqueia destruição, recriação ou troca de identidade da Lambda gerenciada."""

import json
import sys
from pathlib import Path

LAMBDA_ADDRESS = "aws_lambda_function.cpf_validator"
IDENTITY_FIELDS = ("function_name", "package_type", "handler", "runtime")


def review_plan(plan: dict) -> list[str]:
    diagnostics = []
    for resource in plan.get("resource_changes", []):
        address = resource.get("address", "recurso desconhecido")
        change = resource.get("change", {})
        actions = change.get("actions", [])
        before = change.get("before") or {}
        after = change.get("after") or {}

        if "delete" in actions:
            diagnostics.append(f"Ação destrutiva/replacement detectada em {address}; plan bloqueado.")
        if address == LAMBDA_ADDRESS:
            # Os atributos aparecem apenas em `after` na criação inicial;
            # isso não representa alteração de identidade de recurso existente.
            if actions == ["create"] and not before:
                continue
            for field in IDENTITY_FIELDS:
                if before.get(field) != after.get(field) and (field in before or field in after):
                    diagnostics.append(f"Mudança de identidade da Lambda ({field}) detectada; plan bloqueado.")
    return diagnostics


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: review_lambda_plan.py <arquivo-plan-json>", file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Não foi possível ler o plan JSON; nenhum conteúdo sensível foi exibido.", file=sys.stderr)
        return 2
    diagnostics = review_plan(plan)
    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic, file=sys.stderr)
        return 1
    print("Guard do plan Lambda aprovado: sem destruição, recriação ou troca de identidade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
