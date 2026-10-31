import uuid
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.common.choices import RolSistema
from apps.sanciones.demo import cargar_demo
from apps.sanciones.dominio.models import Sancion, TipoSancion
from apps.sanciones.fabrica import sancion_servicio
from apps.sanciones.servicios import estado_de
from apps.sanciones.tests.helpers import crear_cuenta

HOY = date.today()


def nueva(cuenta_id, tipo=TipoSancion.OBSERVACION, dias=None, inicio=None, activa=True):
    return Sancion.objects.create(
        solicitante_id=cuenta_id, aplicada_por_id=uuid.uuid4(), tipo=tipo, motivo="Motivo de prueba",
        duracion_dias=dias, fecha_inicio=inicio or HOY, activa=activa)


class ContratoSancionTests(TestCase):
    """tiene_sancion_activa y sancion_mas_grave: lo que usan Identidad y Circulación."""

    def setUp(self):
        self.cuenta = uuid.uuid4()
        self.servicio = sancion_servicio()

    def test_sin_sanciones(self):
        self.assertFalse(self.servicio.tiene_sancion_activa(self.cuenta))
        self.assertIsNone(self.servicio.sancion_mas_grave(self.cuenta))

    def test_suspension_vigente_cumplida_y_levantada(self):
        s = nueva(self.cuenta, TipoSancion.SUSPENSION_TEMPORAL, dias=7)
        self.assertTrue(self.servicio.tiene_sancion_activa(self.cuenta))
        s.levantar()
        self.assertFalse(self.servicio.tiene_sancion_activa(self.cuenta))

    def test_limite_exacto_de_la_duracion(self):
        """3 días desde hace 2 días: hoy es el último día -> vigente. Desde hace 3: ya cumplida."""
        nueva(self.cuenta, TipoSancion.SUSPENSION_TEMPORAL, dias=3, inicio=HOY - timedelta(days=2))
        self.assertTrue(self.servicio.tiene_sancion_activa(self.cuenta))
        otra = uuid.uuid4()
        nueva(otra, TipoSancion.SUSPENSION_TEMPORAL, dias=3, inicio=HOY - timedelta(days=3))
        self.assertFalse(self.servicio.tiene_sancion_activa(otra))

    def test_baneo_sin_plazo_siempre_vigente(self):
        nueva(self.cuenta, TipoSancion.BANEO, inicio=HOY - timedelta(days=500))
        self.assertTrue(self.servicio.tiene_sancion_activa(self.cuenta))

    def test_otra_cuenta_no_se_ve_afectada(self):
        nueva(self.cuenta, TipoSancion.BANEO)
        self.assertFalse(self.servicio.tiene_sancion_activa(uuid.uuid4()))

    def test_sancion_mas_grave(self):
        nueva(self.cuenta, TipoSancion.OBSERVACION)
        self.assertEqual(self.servicio.sancion_mas_grave(self.cuenta), TipoSancion.OBSERVACION)
        nueva(self.cuenta, TipoSancion.SUSPENSION_TEMPORAL, dias=5)
        self.assertEqual(self.servicio.sancion_mas_grave(self.cuenta), TipoSancion.SUSPENSION_TEMPORAL)
        baneo = nueva(self.cuenta, TipoSancion.BANEO)
        self.assertEqual(self.servicio.sancion_mas_grave(self.cuenta), TipoSancion.BANEO)
        baneo.levantar()   # al levantar el baneo, vuelve a mandar la suspensión
        self.assertEqual(self.servicio.sancion_mas_grave(self.cuenta), TipoSancion.SUSPENSION_TEMPORAL)

    def test_la_lista_y_el_contrato_dicen_lo_mismo(self):
        casos = [
            nueva(uuid.uuid4(), TipoSancion.SUSPENSION_TEMPORAL, dias=3, inicio=HOY - timedelta(days=2)),
            nueva(uuid.uuid4(), TipoSancion.SUSPENSION_TEMPORAL, dias=3, inicio=HOY - timedelta(days=3)),
            nueva(uuid.uuid4(), TipoSancion.BANEO),
            nueva(uuid.uuid4(), TipoSancion.OBSERVACION, activa=False),
        ]
        for s in casos:
            self.assertEqual(estado_de(s) == "vigente",
                             self.servicio.tiene_sancion_activa(s.solicitante_id), s.tipo)


class VistasSancionTests(TestCase):
    def test_roles(self):
        url = reverse("sanciones:lista")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(crear_cuenta(roles=[RolSistema.SOLICITANTE]))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(crear_cuenta(roles=[RolSistema.SUPERVISOR]))
        self.assertEqual(self.client.get(url).status_code, 403)
        for rol in (RolSistema.ENCARGADO, RolSistema.ADMINISTRADOR):
            self.client.force_login(crear_cuenta(roles=[rol]))
            self.assertEqual(self.client.get(url).status_code, 200, rol)

    def test_solicitante_no_puede_sancionar(self):
        self.client.force_login(crear_cuenta(roles=[RolSistema.SOLICITANTE]))
        r = self.client.post(reverse("sanciones:crear"), dict(
            solicitante_id=str(uuid.uuid4()), tipo="BANEO", motivo="Intento no autorizado",
            fecha_inicio=HOY.isoformat()))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Sancion.objects.count(), 0)

    def test_crear_sancion_deja_un_solo_registro_de_auditoria(self):
        encargado = crear_cuenta(roles=[RolSistema.ENCARGADO])
        self.client.force_login(encargado)
        self.client.post(reverse("sanciones:crear"), dict(
            solicitante_id=str(uuid.uuid4()), prestamo_id="", tipo="OBSERVACION",
            motivo="No devolvió el cable", duracion_dias="", fecha_inicio=HOY.isoformat()))
        sancion = Sancion.objects.get()
        self.assertEqual(sancion.aplicada_por_id, encargado.pk)
        registro = RegistroAuditoria.objects.get()
        self.assertEqual((registro.accion, registro.entidad, registro.actor_id),
                         ("SANCION", "Sancion", encargado.pk))


class DemoTests(TestCase):
    def test_cargar_demo_es_idempotente_y_no_bloquea(self):
        encargado, ana, diego = (crear_cuenta(roles=[r]) for r in (
            RolSistema.ENCARGADO, RolSistema.SOLICITANTE, RolSistema.SOLICITANTE))
        self.assertEqual(cargar_demo(encargado, ana, diego), 2)
        self.assertEqual(cargar_demo(encargado, ana, diego), 0)
        self.assertEqual(Sancion.objects.count(), 2)
        servicio = sancion_servicio()
        self.assertFalse(servicio.tiene_sancion_activa(ana.pk))
        self.assertFalse(servicio.tiene_sancion_activa(diego.pk))
