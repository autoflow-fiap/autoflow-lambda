import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import psycopg2


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body),
    }


def _request_body(event):
    body = event.get("body", event)

    if isinstance(body, str):
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        return json.loads(body)

    return body


def _document_digits(document):
    return re.sub(r"\D", "", str(document or ""))


def _is_valid_cpf(cpf):
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    first_digit = _calculate_document_digit(cpf[:9], range(10, 1, -1))
    second_digit = _calculate_document_digit(cpf[:10], range(11, 1, -1))
    return cpf[-2:] == f"{first_digit}{second_digit}"


def _is_valid_cnpj(cnpj):
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    first_digit = _calculate_document_digit(
        cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    )
    second_digit = _calculate_document_digit(
        cnpj[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    )
    return cnpj[-2:] == f"{first_digit}{second_digit}"


def _calculate_document_digit(document, weights):
    total = sum(
        int(digit) * weight
        for digit, weight in zip(document, weights)
    )
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def _is_valid_document(document):
    return _is_valid_cpf(document) or _is_valid_cnpj(document)


def _get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "autoflow_db"),
        user=os.environ["DB_USERNAME"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def _find_user_by_document(cpf_cnpj):
    connection = _get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.cpf_cnpj,
                    u.email,
                    u.senha,
                    u.role,
                    c.status
                FROM usuarios u
                LEFT JOIN clientes c
                    ON regexp_replace(c.cpf_cnpj, '[^0-9]', '', 'g') =
                       regexp_replace(u.cpf_cnpj, '[^0-9]', '', 'g')
                WHERE regexp_replace(u.cpf_cnpj, '[^0-9]', '', 'g') = %s
                """,
                (cpf_cnpj,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return {
                "usuario_id": row[0],
                "cpf_cnpj": _document_digits(row[1]),
                "email": row[2],
                "senha": row[3],
                "role": row[4],
                "cliente_status": row[5],
            }

    finally:
        connection.close()


def _password_matches(password, password_hash):
    if not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _generate_token(user):
    now = datetime.now(timezone.utc)

    expires_in = int(
        os.getenv("JWT_EXPIRES_IN_SECONDS", "3600")
    )

    payload = {
        "sub": user["cpf_cnpj"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }

    if user.get("email"):
        payload["email"] = user["email"]

    token = jwt.encode(
        payload,
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

    return token, expires_in


def _is_active_client(user):
    if user["role"] != "CLIENTE":
        return True

    return user.get("cliente_status") == "ATIVO"


def lambda_handler(event, context):

    try:
        payload = _request_body(event)

        if not isinstance(payload, dict):
            return _response(
                400,
                {
                    "message": "O corpo da requisição deve ser um JSON válido."
                },
            )

        cpf_cnpj = _document_digits(
            payload.get("cpf_cnpj")
        )

        senha = payload.get("senha")

    except (TypeError, ValueError, json.JSONDecodeError):
        return _response(
            400,
            {
                "message": "O corpo da requisição é inválido."
            },
        )

    if not _is_valid_document(cpf_cnpj):
        return _response(
            400,
            {
                "message": "CPF deve conter 11 dígitos ou CNPJ deve conter 14 dígitos."
            },
        )

    if not senha or not isinstance(senha, str):
        return _response(
            400,
            {
                "message": "A senha é obrigatória."
            },
        )

    try:

        user = _find_user_by_document(cpf_cnpj)

        if not user:
            return _response(
                401,
                {
                    "message": "CPF/CNPJ ou senha inválidos."
                },
            )

        if not _password_matches(
            senha,
            user["senha"],
        ):
            return _response(
                401,
                {
                    "message": "CPF/CNPJ ou senha inválidos."
                },
            )

        if not _is_active_client(user):
            return _response(
                401,
                {
                    "message": "CPF/CNPJ ou senha invÃ¡lidos."
                },
            )

        token, expires_in = _generate_token(user)

        return _response(
            200,
            {
                "token": token,
                "tokenType": "Bearer",
                "expiresIn": expires_in,
            },
        )

    except psycopg2.Error as error:

        print("ERRO POSTGRES:", type(error).__name__)

        return _response(
            500,
            {
                "message": "Erro ao acessar o banco de dados."
            },
        )

    except Exception as error:

        print("ERRO INESPERADO:", type(error).__name__)

        return _response(
            500,
            {
                "message": "Erro interno."
            },
        )
