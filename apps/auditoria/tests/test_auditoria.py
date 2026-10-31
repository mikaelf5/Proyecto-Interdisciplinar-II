import uuid

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.auditoria.fabrica import auditoria_servicio
from apps.auditoria.models import RegistroAuditoria, TipoAccion
from apps.common.choices import RolSistema
from apps.sanciones.tests.helpers import crear_cuenta


class AuditoriaServicioTests(TestCase):
    def test_registrar_guarda_una_sola_vez(self):
        """Bug corregido: antes hacía INSERT y luego un UPDATE inútil del mismo registro."""
        with CaptureQueriesContext(connection) as consultas:
            registro = auditoria_servicio().registrar(
                uuid.uuid4(), TipoAccion.ENTREGA, "Prestamo", uuid.uuid4(), "prueba")
        sql = [q["sql"] for q in consultas.captured_queries]
        self.assertEqual(sum(s.startswith("INSERT") for s in sql), 1)
        self.assertEqual(sum(s.startswith("UPDATE") for s in sql), 0)
        self.assertEqual(RegistroAuditoria.objects.filter(pk=registro.pk).count(), 1)

    def test_los_registros_no_se_pueden_borrar(self):
        registro = auditoria_servicio().registrar(uuid.uuid4(), TipoAccion.RECHAZO, "Reserva", uuid.uuid4())
        with self.assertRaises(Exception):
            registro.delete()


class AuditoriaVistaTests(TestCase):
    def test_solo_el_administrador_ve_la_bitacora(self):
        url = reverse("auditoria:lista")
        self.assertEqual(self.client.get(url).status_code, 302)       # sin sesión -> login
        self.client.force_login(crear_cuenta(roles=[RolSistema.SOLICITANTE]))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(crear_cuenta(roles=[RolSistema.ENCARGADO]))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(crear_cuenta(roles=[RolSistema.ADMINISTRADOR]))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_filtros(self):
        servicio = auditoria_servicio()
        actor = uuid.uuid4()
        servicio.registrar(actor, TipoAccion.SANCION, "Sancion", uuid.uuid4(), "a")
        servicio.registrar(uuid.uuid4(), TipoAccion.ENTREGA, "Prestamo", uuid.uuid4(), "b")
        self.client.force_login(crear_cuenta())
        url = reverse("auditoria:lista")
        n = lambda **p: len(self.client.get(url, p).context["registros"])
        self.assertEqual(n(), 2)
        self.assertEqual(n(accion="SANCION"), 1)
        self.assertEqual(n(entidad="Prestamo"), 1)
        self.assertEqual(n(actor=str(actor)[:8]), 1)
        self.assertEqual(n(desde="2000-01-01", hasta="2000-01-02"), 0)
