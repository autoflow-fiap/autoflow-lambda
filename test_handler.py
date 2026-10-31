import base64
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import jwt
import psycopg2

from handler import _find_user_by_document, _generate_token, lambda_handler


class LambdaHandlerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test-secret"
        os.environ["JWT_EXPIRES_IN_SECONDS"] = "3600"

    @staticmethod
    def gateway_event(body, encoded=False):
        serialized_body = json.dumps(body) if not isinstance(body, str) else body

        if encoded:
            serialized_body = base64.b64encode(serialized_body.encode("utf-8")).decode("ascii")

        return {
            "version": "2.0",
            "routeKey": "POST /auth/login",
            "rawPath": "/auth/login",
            "body": serialized_body,
            "isBase64Encoded": encoded,
            "requestContext": {},
        }

    @staticmethod
    def response_body(response):
        return json.loads(response["body"])

    def test_deve_emitir_token_para_login_valido_via_api_gateway(self):
        user = {
            "usuario_id": 1,
            "cpf_cnpj": "52998224725",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": "ATIVO",
        }

        with patch("handler._find_user_by_document", return_value=user) as find_user, patch(
            "handler._password_matches", return_value=True
        ), patch("handler._generate_token", return_value=("jwt-token", 3600)):
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "529.982.247-25", "senha": "Senha@1234"},
                    encoded=True,
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.response_body(response)["token"], "jwt-token")
        self.assertEqual(self.response_body(response)["tokenType"], "Bearer")
        find_user.assert_called_once_with("52998224725")

    def test_deve_aceitar_evento_direto_com_contrato_atual_do_frontend(self):
        user = {
            "cpf_cnpj": "52998224725",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": "ATIVO",
        }
        with patch("handler._find_user_by_document", return_value=user) as find_user, patch(
            "handler._password_matches", return_value=True
        ), patch("handler._generate_token", return_value=("jwt-token", 3600)):
            response = lambda_handler(
                {"cpf_cnpj": "52998224725", "senha": "senha-teste"}, None
            )

        self.assertEqual(response["statusCode"], 200)
        find_user.assert_called_once_with("52998224725")

    def test_deve_aceitar_cpf_cnpj_em_evento_http_api_v2(self):
        with patch("handler._find_user_by_document", return_value=None) as find_user:
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "invalida"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 401)
        find_user.assert_called_once_with("52998224725")

    def test_deve_retornar_400_para_body_base64_malformado(self):
        event = self.gateway_event("{}")
        event["body"] = "%%%"
        event["isBase64Encoded"] = True

        response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(
            self.response_body(response)["message"],
            "O corpo da requisição é inválido.",
        )

    def test_deve_retornar_400_quando_campos_obrigatorios_estao_ausentes(self):
        response = lambda_handler(self.gateway_event({}), None)

        self.assertEqual(response["statusCode"], 400)
        self.assertIn("11 dígitos", self.response_body(response)["message"])

    def test_deve_retornar_401_para_senha_invalida(self):
        user = {
            "cpf_cnpj": "52998224725",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": "ATIVO",
        }
        with patch("handler._find_user_by_document", return_value=user), patch(
            "handler._password_matches", return_value=False
        ):
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "incorreta"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(
            self.response_body(response)["message"],
            "CPF/CNPJ ou senha inválidos.",
        )

    def test_deve_rejeitar_cpf_com_digito_verificador_invalido(self):
        with patch("handler._find_user_by_document") as find_user:
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "529.982.247-26", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        find_user.assert_not_called()

    def test_deve_rejeitar_cliente_inexistente(self):
        user = {
            "cpf_cnpj": "52998224725",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": None,
        }

        with patch("handler._find_user_by_document", return_value=user), patch(
            "handler._password_matches", return_value=True
        ), patch("handler._generate_token") as generate_token:
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 401)
        generate_token.assert_not_called()

    def test_deve_rejeitar_cliente_inativo(self):
        user = {
            "cpf_cnpj": "52998224725",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": "INATIVO",
        }

        with patch("handler._find_user_by_document", return_value=user), patch(
            "handler._password_matches", return_value=True
        ), patch("handler._generate_token") as generate_token:
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 401)
        generate_token.assert_not_called()

    def test_deve_aceitar_cnpj_valido(self):
        user = {
            "cpf_cnpj": "11222333000181",
            "senha": "hash",
            "role": "CLIENTE",
            "cliente_status": "ATIVO",
        }

        with patch("handler._find_user_by_document", return_value=user) as find_user, patch(
            "handler._password_matches", return_value=True
        ), patch("handler._generate_token", return_value=("jwt-token", 3600)):
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "11.222.333/0001-81", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 200)
        find_user.assert_called_once_with("11222333000181")

    def test_deve_gerar_jwt_com_subject_e_expiracao(self):
        os.environ["JWT_SECRET"] = "s" * 64

        token, expires_in = _generate_token(
            {
                "cpf_cnpj": "52998224725",
                "role": "CLIENTE",
                "email": "cliente@autoflow.com",
            }
        )
        claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])

        self.assertEqual(claims["sub"], "52998224725")
        self.assertEqual(claims["role"], "CLIENTE")
        self.assertEqual(claims["email"], "cliente@autoflow.com")
        self.assertEqual(expires_in, 3600)

    def test_deve_consultar_status_do_cliente_ao_buscar_usuario(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "52998224725",
            "cliente@autoflow.com",
            "hash",
            "CLIENTE",
            "ATIVO",
        )

        with patch("handler._get_connection", return_value=connection):
            user = _find_user_by_document("52998224725")

        self.assertEqual(user["cliente_status"], "ATIVO")
        query = cursor.execute.call_args.args[0]
        self.assertIn("c.status", query)
        self.assertIn("LEFT JOIN clientes", query)
        connection.close.assert_called_once_with()

    def test_deve_retornar_400_para_json_invalido(self):
        response = lambda_handler(self.gateway_event("{"), None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(
            self.response_body(response)["message"],
            "O corpo da requisição é inválido.",
        )

    def test_deve_retornar_400_para_documento_invalido(self):
        response = lambda_handler(
            self.gateway_event({"cpf_cnpj": "123", "senha": "Senha@1234"}),
            None,
        )

        self.assertEqual(response["statusCode"], 400)
        self.assertIn("11 dígitos", self.response_body(response)["message"])

    def test_deve_retornar_401_para_credenciais_invalidas(self):
        with patch("handler._find_user_by_document", return_value=None):
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(
            self.response_body(response)["message"],
            "CPF/CNPJ ou senha inválidos.",
        )

    def test_deve_retornar_500_quando_banco_falhar(self):
        canary = "sensitive-login-data-canary"
        with patch("builtins.print") as print_mock, patch(
            "handler._find_user_by_document",
            side_effect=psycopg2.Error(canary),
        ):
            response = lambda_handler(
                self.gateway_event(
                    {"cpf_cnpj": "52998224725", "senha": "Senha@1234"}
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(
            self.response_body(response)["message"],
            "Erro ao acessar o banco de dados.",
        )
        logged_text = " ".join(
            str(argument)
            for call in print_mock.call_args_list
            for argument in call.args
        )
        self.assertNotIn(canary, logged_text)


if __name__ == "__main__":
    unittest.main()
