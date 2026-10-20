import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.common.choices import TipoNotificacion
from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
from apps.notificaciones.dominio.puertos import IEmisorNotificacion


class EmisorFalso(IEmisorNotificacion):
    """Adaptador falso: demuestra que el puerto permite cambiar el canal sin tocar el servicio."""
    def __init__(self):
        self.enviadas = []

    def enviar(self, notificacion):
        self.enviadas.append(notificacion)
        return True


class NotificacionServicioTests(TestCase):
    def test_enviar_por_correo_real(self):
        cuenta = get_user_model().objects.create_user("ana@demo.pe", "Ana", "1", "x")
        dto = NotificacionServicioAplicacion().enviar(cuenta.id, TipoNotificacion.ALERTA_ATRASO, "Venció")
        self.assertIsNotNone(dto.fecha_envio)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@demo.pe"])

    def test_sin_correo_queda_registrada_sin_enviar(self):
        dto = NotificacionServicioAplicacion().enviar(uuid.uuid4(), TipoNotificacion.ALERTA_ATRASO, "x")
        self.assertIsNone(dto.fecha_envio)

    def test_puerto_con_emisor_falso(self):
        emisor = EmisorFalso()
        NotificacionServicioAplicacion(emisor=emisor).enviar(uuid.uuid4(), TipoNotificacion.ITEM_DANIADO, "x")
        self.assertEqual(len(emisor.enviadas), 1)

    def test_marcar_leida_solo_el_destinatario(self):
        s = NotificacionServicioAplicacion(emisor=EmisorFalso())
        duenio = uuid.uuid4()
        n = s.enviar(duenio, TipoNotificacion.ITEM_DANIADO, "x")
        with self.assertRaises(ValidationError):
            s.marcar_leida(n.id, destinatario_id=uuid.uuid4())
        self.assertTrue(s.marcar_leida(n.id, destinatario_id=duenio).leida)
