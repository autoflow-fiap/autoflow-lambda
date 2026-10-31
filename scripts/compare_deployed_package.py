"""Compara o pacote local com o implantado sem gravar URL assinada ou conteúdo."""
import argparse
import ast
import io
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile


def contents(archive):
    with zipfile.ZipFile(archive) as package:
        return {name: package.read(name) for name in package.namelist() if not name.endswith("/")}


def contract_shape(source):
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    handler = functions.get("lambda_handler")
    handler_names = {node.id for node in ast.walk(handler) if isinstance(node, ast.Name)} if handler else set()
    calls_json_loads = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "loads"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        for node in ast.walk(tree)
    )
    reads_body = "body" in strings and ("event" in handler_names if handler else False)
    return {
        "lambda_handler_present": handler is not None,
        "reads_http_api_body": reads_body,
        "json_body_parser": calls_json_loads,
        "exact_fields_cpf_cnpj_senha": {"cpf_cnpj", "senha"}.issubset(strings),
        "proxy_response_status_body_headers": {"statusCode", "body", "headers"}.issubset(strings),
        "token_response_fields": {"token", "tokenType", "expiresIn"}.issubset(strings),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    result = subprocess.run(["aws", "lambda", "get-function", "--function-name", args.function,
                             "--region", args.region, "--output", "json"], capture_output=True, text=True, check=True)
    location = json.loads(result.stdout)["Code"]["Location"]
    with urllib.request.urlopen(location, timeout=30) as response:
        deployed = contents(io.BytesIO(response.read()))
    local = contents(Path(__file__).resolve().parents[1] / "lambda.zip")
    deployed_contract = contract_shape(deployed["handler.py"])
    print("Forma do contrato HTTP API v2 no handler implantado:", json.dumps(deployed_contract, sort_keys=True))
    changed = sorted(name for name in set(local) | set(deployed) if local.get(name) != deployed.get(name))
    source = (Path(__file__).resolve().parents[1] / "handler.py").read_bytes()
    print("Handler do pacote corresponde semanticamente ao fonte local:",
          ast.dump(ast.parse(local["handler.py"])) == ast.dump(ast.parse(source)))
    print("Handler implantado corresponde semanticamente ao pacote local:",
          ast.dump(ast.parse(deployed["handler.py"])) == ast.dump(ast.parse(local["handler.py"])))
    print("Arquivos com conteúdo divergente:", len(changed))
    for name in changed:
        print(name)
    raise SystemExit(bool(changed))
