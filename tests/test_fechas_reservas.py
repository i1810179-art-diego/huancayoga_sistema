
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app as sistema


class FechasReservasTests(unittest.TestCase):
    def setUp(self):
        self.cursor = Mock()
        self.cursor.fetchall.return_value = [(1, 'Servicio de prueba', 30, 60)]
        self.cursor.fetchone.return_value = ('Cliente', 'Prueba', 'Local', '912345678', 'test@example.test')
        self.connection = Mock()
        self.connection.cursor.return_value = self.cursor
        self.database = patch.object(sistema, 'mysql', SimpleNamespace(connection=self.connection))
        self.database.start()
        self.addCleanup(self.database.stop)
        self.web = sistema.app.test_client()
        with self.web.session_transaction() as session:
            session.update(cliente_id=7, _csrf_token='test')

    def datos(self, fecha, modalidad='regular'):
        prefijo = 'institucion_' if modalidad == 'institucional' else ''
        datos = {
            'csrf_token':'test','tipo_reserva':modalidad,
            prefijo+'nombre_cliente':'Cliente Prueba Local',prefijo+'celular':'912345678',
            prefijo+'correo':'test@example.test',prefijo+'servicio_id':'1',
            prefijo+'cantidad_personas':'1',prefijo+'fecha':fecha.isoformat(),prefijo+'hora':'10:00',
        }
        if prefijo:
            datos.update(institucion_duracion_minutos='60',categoria='colegio',
                         nombre_organizacion='Colegio de prueba',tipo_lugar='local')
        return datos

    def test_seis_meses_calendario_y_fin_de_mes(self):
        for hoy,maxima in [
            (date(2026,11,12),date(2027,5,12)),
            (date(2026,8,31),date(2027,2,28)),
            (date(2027,8,31),date(2028,2,29)),
            (date(2026,10,31),date(2027,4,30)),
        ]:
            with self.subTest(hoy=hoy):
                self.assertEqual(sistema.limites_fechas_reserva(hoy),(hoy,maxima))

    def test_calendarios_tienen_minimo_y_maximo(self):
        response=self.web.get('/reservar')
        minima,maxima=sistema.limites_fechas_reserva()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.text.count('min="'+minima.isoformat()+'" max="'+maxima.isoformat()+'"'),2)

    def test_rechaza_dia_siguiente_al_limite_ambas_modalidades(self):
        fecha=sistema.limites_fechas_reserva()[1]+timedelta(days=1)
        for modalidad in ['regular','institucional']:
            with self.subTest(modalidad=modalidad):
                response=self.web.post('/reservar',data=self.datos(fecha,modalidad))
                self.assertEqual(response.status_code,400)
                self.assertIn('Solo puedes reservar hasta seis meses',response.text)
        self.connection.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO reservas' in call.args[0] for call in self.cursor.execute.call_args_list))

    def test_acepta_ultimo_dia_ambas_modalidades(self):
        fecha=sistema.limites_fechas_reserva()[1]
        for modalidad in ['regular','institucional']:
            with self.subTest(modalidad=modalidad):
                response=self.web.post('/reservar',data=self.datos(fecha,modalidad))
                self.assertEqual(response.status_code,302)
                self.assertTrue(response.location.endswith('/cliente/mis-citas'))
        self.assertEqual(self.connection.commit.call_count,2)
        self.assertEqual(self.cursor.executemany.call_count,2)

    def test_rechaza_fecha_pasada_y_anio_lejano(self):
        for fecha in [sistema.limites_fechas_reserva()[0]-timedelta(days=1),date(2030,1,1)]:
            with self.subTest(fecha=fecha):
                response=self.web.post('/reservar',data=self.datos(fecha))
                self.assertEqual(response.status_code,400)
        self.connection.commit.assert_not_called()

    def test_se_conserva_rechazo_de_cruce_por_bloques(self):
        self.cursor.executemany.side_effect=sistema.IntegrityError(1062,'Horario ocupado')
        response=self.web.post('/reservar',data=self.datos(sistema.limites_fechas_reserva()[1]))
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.location.endswith('/reservar'))
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_registro_consulta_automatica_sin_boton(self):
        response=self.web.get('/cliente/registro')
        self.assertNotIn('onclick="buscarDNI()"',response.text)
        self.assertNotIn('>Buscar DNI</button>',response.text)
        self.assertIn('registro_dni.js',response.text)
