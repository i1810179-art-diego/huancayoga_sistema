
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as sistema


class RegistroDniTests(unittest.TestCase):
    def setUp(self):
        self.web = sistema.app.test_client()
        with self.web.session_transaction() as session:
            session['_csrf_token'] = 'test'
        self.identidad = dict(dni='12345678', nombres='Persona de prueba',
                              apellido_paterno='Apellido Uno', apellido_materno='Apellido Dos')
        with sistema.app.app_context():
            self.token = sistema.firmador_dni_registro().dumps(self.identidad)
        self.formulario = dict(csrf_token='test', **self.identidad, celular='912345678',
                               correo='test@example.test', password='Prueba123!',
                               confirmar_password='Prueba123!', validacion_dni=self.token)

    def test_consulta_firma_identidad_y_evitar_cache(self):
        respuesta = Mock(status_code=200, text='datos de prueba')
        respuesta.json.return_value = self.identidad
        with patch.dict('os.environ', RENIEC_API_URL='https://proveedor.example.test', RENIEC_API_TOKEN='test'), patch.object(sistema.requests, 'get', return_value=respuesta):
            response = self.web.get('/api/reniec/12345678')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        with sistema.app.app_context():
            self.assertEqual(sistema.firmador_dni_registro().loads(response.json['validacion_dni'], max_age=1800), self.identidad)

    def test_otro_dni_con_identidad_anterior_no_se_guarda(self):
        for cambios in [{'dni':'87654321'}, {'validacion_dni':''}, {'validacion_dni':self.token+'alterado'}]:
            with self.subTest(cambios=cambios), patch.object(sistema, 'mysql') as db:
                response = self.web.post('/cliente/registro', data={**self.formulario, **cambios})
                self.assertEqual(response.status_code, 302)
                self.assertIn('/cliente/registro', response.location)
                db.connection.cursor.assert_not_called()

    def test_identidad_vencida_no_se_guarda(self):
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp', return_value=int(time.time())+1801), patch.object(sistema, 'mysql') as db:
            response = self.web.post('/cliente/registro', data=self.formulario)
            self.assertIn('/cliente/registro', response.location)
            db.connection.cursor.assert_not_called()

    def test_guarda_nombres_de_la_consulta_firmada(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [None, (77, '12345678', 'Persona de prueba')]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(sistema, 'mysql', SimpleNamespace(connection=connection)), patch.object(sistema, 'enviar_correo', return_value=False):
            response = self.web.post('/cliente/registro', data={
                **self.formulario, 'nombres':'Nombre manipulado', 'apellido_paterno':'Otro', 'apellido_materno':'Distinto',
            })
        self.assertTrue(response.location.endswith('/cliente/dashboard'))
        insert = next(call for call in cursor.execute.call_args_list if 'INSERT INTO clientes' in call.args[0])
        self.assertEqual(insert.args[1][:4], ('12345678','Persona de prueba','Apellido Uno','Apellido Dos'))
        connection.commit.assert_called_once()

    def test_consulta_fallida_no_devuelve_validacion(self):
        with patch.dict('os.environ', RENIEC_API_URL='https://proveedor.example.test', RENIEC_API_TOKEN='test'), patch.object(sistema.requests, 'get', return_value=Mock(status_code=404, text='sin datos')):
            response = self.web.get('/api/reniec/12345678')
        self.assertEqual(response.status_code,400)
        self.assertNotIn('validacion_dni', response.json)
