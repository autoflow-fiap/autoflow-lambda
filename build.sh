#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

rm -rf build
mkdir -p build
rm -f lambda.zip

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --platform linux/amd64 \
  --entrypoint /bin/sh \
  -v "$SCRIPT_DIR:/workspace" \
  -w /workspace \
  python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 \
  -c 'set -eu
python -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
python -m pip install --no-cache-dir --only-binary=:all: --no-compile --requirement requirements.txt --target build
cp handler.py build/
PYTHONPYCACHEPREFIX=/tmp/lambda-pycache python -m compileall -q build
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=build python -c "import bcrypt, jwt, psycopg2; assert bcrypt.__version__ == \"5.0.0\"; assert jwt.__version__ == \"2.15.1\"; assert psycopg2.__version__.startswith(\"2.9.13\"); print(\"Imports e versões: bcrypt=%s PyJWT=%s psycopg2=%s\" % (bcrypt.__version__, jwt.__version__, psycopg2.__version__))"
python scripts/create_lambda_zip.py build lambda.zip
python -m zipfile -t lambda.zip'

echo "ZIP Lambda determinístico criado: $SCRIPT_DIR/lambda.zip"
