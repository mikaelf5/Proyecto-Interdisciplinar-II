import uuid
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoPrestamo, RolSistema, TipoNotificacion
from apps.notificaciones.dominio.models import Notificacion
from apps.sanciones.aplicacion.vencimientos import SISTEMA_ID
from apps.sanciones.fabrica import revisor_vencimientos
from apps.sanciones.tests.helpers import crear_cuenta, crear_item, crear_prestamo


class RevisarVencimientosTests(TestCase):
    def setUp(self):
        self.ana = crear_cuenta("ana@demo.pe", "Ana Alumna", roles=[RolSistema.SOLICITANTE])
        self.item = crear_item("EQP-001", "Laptop")
        self.ahora = timezone.now()

    def prestamo(self, vence_en, **kw):
        return crear_prestamo(self.item.id, self.ana.pk, vence=self.ahora + vence_en,
                              entrega=self.ahora - timedelta(hours=3), **kw)

    def test_recordatorio_30_min_antes_y_una_sola_vez(self):
        p = self.prestamo(timedelta(minutes=20))
        r = revisor_vencimientos().revisar()
        self.assertEqual((r.recordatorios, r.vencidos), (1, 0))
        n = Notificacion.objects.get()
        self.assertEqual((n.tipo, n.destinatario_id), (TipoNotificacion.RECORDATORIO_VENCIMIENTO, self.ana.pk))
        self.assertIn(f"#{str(p.id)[:8]}", n.mensaje)
        self.assertIn("EQP-001", n.mensaje)
        self.assertEqual(len(mail.outbox), 1)                      # se mandó el correo
        self.assertEqual(mail.outbox[0].to, ["ana@demo.pe"])
        # segunda ejecución: no repite el aviso
        r2 = revisor_vencimientos().revisar()
        self.assertEqual((r2.recordatorios, r2.vencidos), (0, 0))
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_no_avisa_si_falta_mas_de_30_minutos(self):
        self.prestamo(timedelta(hours=2))
        r = revisor_vencimientos().revisar()
        self.assertEqual((r.recordatorios, r.vencidos), (0, 0))
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_ventana_configurable(self):
        self.prestamo(timedelta(minutes=50))
        self.assertEqual(revisor_vencimientos().revisar(minutos_aviso=30).recordatorios, 0)
        self.assertEqual(revisor_vencimientos().revisar(minutos_aviso=60).recordatorios, 1)

    def test_vencido_cambia_estado_audita_y_avisa(self):
        p = self.prestamo(-timedelta(minutes=10))
        r = revisor_vencimientos().revisar()
        self.assertEqual((r.recordatorios, r.vencidos), (0, 1))
        p.refresh_from_db()
        self.assertEqual(p.estado, EstadoPrestamo.VENCIDO)
        n = Notificacion.objects.get()
        self.assertEqual(n.tipo, TipoNotificacion.ALERTA_ATRASO)
        registro = RegistroAuditoria.objects.get()
        self.assertEqual((registro.actor_id, registro.entidad, registro.entidad_id, registro.accion),
                         (SISTEMA_ID, "Prestamo", p.id, "CAMBIO_ESTADO"))
        # idempotente: ya no está ACTIVO, no se vuelve a avisar
        r2 = revisor_vencimientos().revisar()
        self.assertEqual((r2.recordatorios, r2.vencidos), (0, 0))
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_ignora_devueltos_cerrados_y_ya_vencidos(self):
        otros = [crear_item(f"LIB-00{i}", "Libro") for i in range(3)]
        for item, estado in zip(otros, (EstadoPrestamo.DEVUELTO, EstadoPrestamo.CERRADO_POR_PERDIDA,
                                         EstadoPrestamo.VENCIDO)):
            crear_prestamo(item.id, self.ana.pk, estado=estado, entrega=self.ahora - timedelta(hours=5),
                           vence=self.ahora - timedelta(hours=1),
                           devuelto=self.ahora - timedelta(hours=2) if estado == EstadoPrestamo.DEVUELTO else None)
        r = revisor_vencimientos().revisar()
        self.assertEqual((r.recordatorios, r.vencidos), (0, 0))
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_varios_prestamos_a_la_vez(self):
        self.prestamo(timedelta(minutes=10))
        item2 = crear_item("EQP-002", "Proyector")
        crear_prestamo(item2.id, self.ana.pk, entrega=self.ahora - timedelta(hours=6),
                       vence=self.ahora - timedelta(hours=1))
        r = revisor_vencimientos().revisar()
        self.assertEqual((r.recordatorios, r.vencidos), (1, 1))
        self.assertEqual(Prestamo.objects.filter(estado=EstadoPrestamo.VENCIDO).count(), 1)

    def test_comando(self):
        self.prestamo(-timedelta(minutes=5))
        salida = StringIO()
        call_command("revisar_vencimientos", stdout=salida)
        self.assertIn("Préstamos marcados como vencidos: 1", salida.getvalue())
