import re
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as sistema


class CompraDuplicadaTests(unittest.TestCase):
    def setUp(self):
        self.stock = 10
        self.orders = []
        self.result = None
        self.queries = []
        self.connection = Mock()
        self.cursor = Mock()
        self.connection.cursor.return_value = self.cursor
        self.cursor.execute.side_effect = self.execute
        self.cursor.fetchone.side_effect = lambda: self.result
        self.database = patch.object(sistema, 'mysql', SimpleNamespace(connection=self.connection))
        self.mail = patch.object(sistema, 'enviar_correo')
        self.database.start()
        self.send_mail = self.mail.start()
        self.addCleanup(self.database.stop)
        self.addCleanup(self.mail.stop)
        self.client = sistema.app.test_client()
        with self.client.session_transaction() as session:
            session['cliente_id'] = 7
            session['_csrf_token'] = 'csrf-test'

    def execute(self, sql, params):
        sql = ' '.join(sql.split())
        self.queries.append(sql)
        if sql.startswith('SELECT id, nombre, descripcion'):
            self.result = (1, 'Yoga mat', 'Mat', 20, self.stock, None)
        elif sql.startswith('SELECT COALESCE'):
            self.result = (max(self.orders, default=0),)
        elif sql.startswith('SELECT id FROM pedidos'):
            self.assertIn('FOR UPDATE', sql)
            newer = [order for order in self.orders if order > params[2]]
            self.result = (max(newer),) if newer else None
        elif sql.startswith('INSERT INTO pedidos'):
            self.orders.append(max(self.orders, default=0) + 1)
        elif sql.startswith('UPDATE productos'):
            self.stock = params[0]

    def token(self):
        response = self.client.get('/comprar/1')
        self.assertEqual(response.status_code, 200)
        return re.search(r'name="pedido_token" value="([^"]+)"', response.text)[1]

    def buy(self, token, quantity=1):
        return self.client.post('/comprar/1', data={
            'csrf_token': 'csrf-test', 'pedido_token': token,
            'nombre_cliente': 'Prueba', 'celular': '900000000',
            'correo': 'prueba@example.com', 'cantidad': quantity,
        })

    def test_retry_registers_one_order_stock_change_and_email(self):
        token = self.token()
        self.assertEqual(self.buy(token).status_code, 302)
        retry = self.buy(token)
        self.assertTrue(retry.location.endswith('/cliente/mis-pedidos'))
        self.assertEqual(self.orders, [1])
        self.assertEqual(self.stock, 9)
        self.assertEqual(self.connection.commit.call_count, 1)
        self.send_mail.assert_called_once()
        self.assertTrue(any('FROM productos' in sql and 'FOR UPDATE' in sql for sql in self.queries))

    def test_fresh_form_allows_intentional_second_order(self):
        self.buy(self.token())
        self.buy(self.token())
        self.assertEqual(len(self.orders), 2)
        self.assertEqual(self.stock, 8)

    def test_tampered_or_missing_token_cannot_create_order(self):
        self.buy('alterado')
        self.buy('')
        self.assertEqual(self.orders, [])
        self.connection.commit.assert_not_called()

    def test_insufficient_stock_releases_transaction(self):
        token = self.token()
        self.buy(token, quantity=11)
        self.assertEqual(self.orders, [])
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called()
        self.cursor.close.assert_called()


if __name__ == '__main__':
    unittest.main()
