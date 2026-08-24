import unittest
from unittest.mock import Mock

from flask import Flask

from api_v1 import register_api, validar_producto, validar_publicacion


class ApiValidationTests(unittest.TestCase):
    def test_producto_valido_normaliza_numeros(self):
        clean, errors = validar_producto({
            "nombre": "  Mat profesional  ",
            "precio": "89.9",
            "stock": 10,
        })
        self.assertEqual(errors, {})
        self.assertEqual(clean["nombre"], "Mat profesional")
        self.assertEqual(str(clean["precio"]), "89.90")
        self.assertEqual(clean["stock"], 10)

    def test_producto_rechaza_precio_y_stock_invalidos(self):
        _, errors = validar_producto({"nombre": "Mat", "precio": -1, "stock": 1.5})
        self.assertIn("precio", errors)
        self.assertIn("stock", errors)

    def test_publicacion_rechaza_tipo_fuera_del_catalogo(self):
        _, errors = validar_publicacion({
            "titulo": "Novedad",
            "contenido": "Contenido de prueba",
            "tipo": "desconocido",
        })
        self.assertIn("tipo", errors)

    def test_endpoint_protegido_exige_bearer_token(self):
        app = Flask(__name__)
        app.secret_key = "test-secret"
        register_api(app, Mock(), Mock())
        response = app.test_client().get("/api/v1/productos")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"]["code"], "TOKEN_REQUERIDO")


if __name__ == "__main__":
    unittest.main()
