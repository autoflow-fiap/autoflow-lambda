"""Publica e verifica pacotes Lambda imutáveis no S3 usando somente AWS CLI."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

PREFIX = "lambda-packages/sha256/"


class PackageError(Exception):
    """Falha segura de publicação ou validação do artefato Lambda."""


class AwsCliError(PackageError):
    def __init__(self, code: str):
        super().__init__(f"AWS CLI falhou (código de serviço: {code or 'desconhecido'}).")
        self.code = code


AwsJson = Callable[[list[str]], dict]


def aws_json(arguments: list[str]) -> dict:
    result = subprocess.run(
        ["aws", "s3api", *arguments, "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        match = re.search(r"\(([A-Za-z0-9]+)\)", result.stderr)
        raise AwsCliError(match.group(1) if match else "")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise PackageError("AWS CLI retornou uma resposta inválida; conteúdo omitido.") from error


def package_digest(package_path: Path) -> tuple[str, str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with package_path.open("rb") as package:
            while chunk := package.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as error:
        raise PackageError("Não foi possível ler o pacote Lambda.") from error
    if size == 0:
        raise PackageError("O pacote Lambda está vazio.")
    digest_bytes = digest.digest()
    return digest.hexdigest(), base64.b64encode(digest_bytes).decode("ascii"), size


def package_key(sha256_hex: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", sha256_hex):
        raise PackageError("SHA-256 inválido para a chave do pacote Lambda.")
    return f"{PREFIX}{sha256_hex}.zip"


def validate_bucket(bucket: str, region: str, owner: str, run_aws: AwsJson = aws_json) -> None:
    versioning = run_aws([
        "get-bucket-versioning", "--bucket", bucket,
        "--expected-bucket-owner", owner,
    ])
    if versioning.get("Status") != "Enabled":
        raise PackageError("O bucket de pacotes precisa ter S3 Versioning habilitado.")

    location = run_aws([
        "get-bucket-location", "--bucket", bucket,
        "--expected-bucket-owner", owner,
    ]).get("LocationConstraint") or "us-east-1"
    if location != region:
        raise PackageError("O bucket de pacotes não está na região da Lambda.")


def head_package(
    bucket: str,
    key: str,
    owner: str,
    region: str,
    version_id: str | None = None,
    run_aws: AwsJson = aws_json,
) -> dict:
    arguments = [
        "head-object", "--bucket", bucket, "--key", key,
        "--expected-bucket-owner", owner,
        "--checksum-mode", "ENABLED", "--region", region,
    ]
    if version_id:
        arguments.extend(["--version-id", version_id])
    return run_aws(arguments)


def validate_head(head: dict, checksum_b64: str, size: int, version_id: str) -> None:
    if head.get("ChecksumSHA256") != checksum_b64:
        raise PackageError("O checksum SHA-256 do objeto S3 não corresponde ao pacote aprovado.")
    if head.get("ContentLength") != size:
        raise PackageError("O tamanho do objeto S3 não corresponde ao pacote aprovado.")
    if not version_id or version_id == "null" or head.get("VersionId") != version_id:
        raise PackageError("A versão do objeto S3 não corresponde à versão aprovada.")


def publish_package(
    package_path: Path,
    bucket: str,
    region: str,
    owner: str,
    run_aws: AwsJson = aws_json,
) -> dict:
    validate_bucket(bucket, region, owner, run_aws)
    digest_hex, digest_b64, size = package_digest(package_path)
    key = package_key(digest_hex)

    put_args = [
        "put-object", "--bucket", bucket, "--key", key,
        "--body", str(package_path), "--region", region,
        "--expected-bucket-owner", owner,
        "--checksum-algorithm", "SHA256", "--checksum-sha256", digest_b64,
        "--if-none-match", "*",
    ]
    for attempt in range(3):
        try:
            put_response = run_aws(put_args)
            version_id = put_response.get("VersionId")
            break
        except AwsCliError as error:
            if error.code == "PreconditionFailed":
                existing = head_package(bucket, key, owner, region, run_aws=run_aws)
                version_id = existing.get("VersionId")
                validate_head(existing, digest_b64, size, version_id or "")
                break
            if error.code == "ConditionalRequestConflict" and attempt < 2:
                continue
            raise
    if not version_id or version_id == "null":
        raise PackageError("S3 não retornou uma versão imutável do pacote.")

    head = head_package(bucket, key, owner, region, version_id, run_aws)
    validate_head(head, digest_b64, size, version_id)
    return {
        "bucket": bucket,
        "key": key,
        "sha256_hex": digest_hex,
        "source_code_hash": digest_b64,
        "version_id": version_id,
        "size": size,
        "region": region,
    }


def verify_package(
    package_path: Path,
    metadata_path: Path,
    bucket: str,
    region: str,
    owner: str,
    run_aws: AwsJson = aws_json,
) -> dict:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageError("Metadados do pacote ausentes ou inválidos.") from error

    digest_hex, digest_b64, size = package_digest(package_path)
    expected = {
        "bucket": bucket,
        "key": package_key(digest_hex),
        "sha256_hex": digest_hex,
        "source_code_hash": digest_b64,
        "size": size,
        "region": region,
    }
    if any(metadata.get(name) != value for name, value in expected.items()):
        raise PackageError("Metadados não correspondem ao pacote, bucket ou região esperados.")
    version_id = metadata.get("version_id")
    if not isinstance(version_id, str) or not version_id or version_id == "null":
        raise PackageError("Metadados não contêm uma versão S3 imutável.")

    validate_bucket(bucket, region, owner, run_aws)
    head = head_package(bucket, expected["key"], owner, region, version_id, run_aws)
    validate_head(head, digest_b64, size, version_id)
    return metadata


def write_metadata(metadata: dict, metadata_path: Path, output_path: Path | None) -> None:
    metadata_path.write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as output:
            for name, value in (
                ("bucket", metadata["bucket"]),
                ("key", metadata["key"]),
                ("source_code_hash", metadata["source_code_hash"]),
                ("version_id", metadata["version_id"]),
            ):
                if "\n" in value or "\r" in value:
                    raise PackageError("Metadado incompatível com saída segura do GitHub Actions.")
                output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("publish", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--file", type=Path, required=True)
        subparser.add_argument("--bucket", required=True)
        subparser.add_argument("--region", required=True)
        subparser.add_argument("--expected-owner", required=True)
        subparser.add_argument("--metadata", type=Path, required=True)
        if command == "publish":
            subparser.add_argument("--github-output", type=Path)

    arguments = parser.parse_args()
    try:
        if arguments.command == "publish":
            metadata = publish_package(
                arguments.file, arguments.bucket, arguments.region, arguments.expected_owner
            )
            write_metadata(metadata, arguments.metadata, arguments.github_output)
            print("Pacote Lambda publicado ou já existente; checksum e versão S3 validados.")
        else:
            verify_package(
                arguments.file, arguments.metadata, arguments.bucket, arguments.region,
                arguments.expected_owner,
            )
            print("Pacote Lambda S3 validado para a versão aprovada.")
    except (PackageError, OSError) as error:
        print(f"Validação do pacote Lambda falhou: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
