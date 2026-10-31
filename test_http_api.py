"""Contrato real do payload HTTP API v2; não depende de Function URL."""
import json
import unittest
from unittest.mock import patch

from handler import lambda_handler


class HttpApiContractTest(unittest.TestCase):
    def event(self, body):
        return {
            "version": "2.0", "routeKey": "POST /auth/login",
            "rawPath": "/auth/login", "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "requestContext": {"stage": "$default", "http": {
                "method": "POST", "path": "/auth/login", "protocol": "HTTP/1.1"
            }},
            "body": json.dumps(body), "isBase64Encoded": False,
        }

    @patch("handler._find_user_by_document", return_value=None)
    def test_credenciais_ficticias_invalidas(self, lookup):
        response = lambda_handler(self.event({
            "cpf_cnpj": "52998224725", "senha": "senha-teste-invalida"
        }), None)
        self.assertEqual(401, response["statusCode"])
        self.assertEqual("application/json", response["headers"]["Content-Type"])
        self.assertEqual({"message": "CPF/CNPJ ou senha inválidos."}, json.loads(response["body"]))
        lookup.assert_called_once_with("52998224725")

    @patch("handler._find_user_by_document")
    def test_alias_nao_e_aceito(self, lookup):
        response = lambda_handler(self.event({"cpf": "52998224725", "senha": "invalida"}), None)
        self.assertEqual(400, response["statusCode"])
        lookup.assert_not_called()

    @patch("handler._find_user_by_document", side_effect=RuntimeError("segredo-de-teste"))
    def test_falha_interna_nao_vaza_excecao(self, lookup):
        response = lambda_handler(self.event({"cpf_cnpj": "52998224725", "senha": "invalida"}), None)
        self.assertEqual(500, response["statusCode"])
        self.assertEqual({"message": "Erro interno."}, json.loads(response["body"]))


if __name__ == "__main__":
    unittest.main()
