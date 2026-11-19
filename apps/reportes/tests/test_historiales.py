"""Observación de la docente: historial de cada persona y de cada ítem."""
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.auditoria.models import RegistroAuditoria, TipoAccion
from apps.common.choices import EstadoPrestamo, RolSistema
from apps.perdidas.dominio.models import CasoPerdida
from apps.reportes.fabrica import historial_servicio
from apps.sanciones.dominio.models import Sancion
from apps.sanciones.tests.helpers import crear_cuenta, crear_item, crear_prestamo

AHORA = timezone.now()
H = lambda horas: timedelta(hours=horas)


class DatosDeHistorialMixin:
    def setUp(self):
        self.admin = crear_cuenta(nombres="Adriana Admin", roles=[RolSistema.ADMINISTRADOR])
        self.encargado = crear_cuenta(nombres="Elena Encargada", roles=[RolSistema.ENCARGADO])
        self.supervisor = crear_cuenta(nombres="Sergio Supervisor", roles=[RolSistema.SUPERVISOR])
        self.ana = crear_cuenta(nombres="Ana Alumna", roles=[RolSistema.SOLICITANTE])
        self.diego = crear_cuenta(nombres="Diego Docente", roles=[RolSistema.SOLICITANTE])
        self.laptop = crear_item("EQP-901", "Laptop")
        self.camara = crear_item("EQP-902", "Cámara")
        # Ana: uno a tiempo y uno con atraso; Diego: uno perdido. Los tres con la laptop o la cámara.
        self.p1 = crear_prestamo(self.laptop.id, self.ana.pk, EstadoPrestamo.DEVUELTO,
                                 entrega=AHORA - H(50), vence=AHORA - H(47), devuelto=AHORA - H(48))
        self.p2 = crear_prestamo(self.laptop.id, self.ana.pk, EstadoPrestamo.DEVUELTO,
                                 entrega=AHORA - H(30), vence=AHORA - H(27), devuelto=AHORA - H(26))
        self.p3 = crear_prestamo(self.camara.id, self.diego.pk, EstadoPrestamo.CERRADO_POR_PERDIDA,
                                 entrega=AHORA - H(20), vence=AHORA - H(17))
        Sancion.objects.create(solicitante_id=self.ana.pk, aplicada_por_id=self.encargado.pk,
                               tipo="OBSERVACION", motivo="Devolvió con 1 h de atraso",
                               fecha_inicio=date.today())
        CasoPerdida.objects.create(prestamo_id=self.p3.pk, solicitante_id=self.diego.pk,
                                   fecha=date.today(), observaciones="No apareció",
                                   costo_estimado=Decimal("120.00"))


class HistorialPersonaTests(DatosDeHistorialMixin, TestCase):
    def test_trae_prestamos_sanciones_y_perdidas_con_fechas(self):
        datos = historial_servicio().de_persona(self.ana.pk)
        resumen = dict(datos.resumen)
        self.assertEqual((resumen["Préstamos"], resumen["Devueltos a tiempo"], resumen["Con atraso"]), (2, 1, 1))
        self.assertEqual((resumen["Sanciones"], resumen["Sanciones vigentes"]), (1, 1))
        prestamos, sanciones, perdidas = datos.secciones
        self.assertEqual(len(prestamos.filas), 2)
        self.assertEqual(prestamos.filas[0][3], "EQP-901 · Laptop")      # el más reciente primero
        self.assertTrue(prestamos.filas[0][4].startswith("Devuelto con atraso"))
        self.assertEqual(prestamos.filas[1][4], "Devuelto a tiempo")
        self.assertEqual(sanciones.filas[0][5], "Elena Encargada")      # quién la aplicó
        self.assertEqual(perdidas.filas, [])
        self.assertIn(f"DNI {self.ana.dni}", datos.subtitulo)

    def test_las_perdidas_dicen_que_item_se_perdio(self):
        perdidas = historial_servicio().de_persona(self.diego.pk).secciones[2]
        self.assertEqual(perdidas.filas[0][1], "EQP-902 · Cámara")


class PermisosHistorialPersonaTests(DatosDeHistorialMixin, TestCase):
    def url(self, cuenta):
        return reverse("reportes:historial_persona", args=[cuenta.pk])

    def test_sin_sesion_pide_iniciar_sesion(self):
        self.assertEqual(self.client.get(self.url(self.ana)).status_code, 302)

    def test_el_solicitante_ve_solo_el_suyo(self):
        self.client.force_login(self.ana)
        r = self.client.get(self.url(self.ana))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Mi historial")
        self.assertEqual(self.client.get(self.url(self.diego)).status_code, 403)
        # El buscador lo lleva directo a su historial.
        self.assertRedirects(self.client.get(reverse("reportes:historial_personas")), self.url(self.ana))

    def test_el_supervisor_tampoco_ve_el_de_otros(self):
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(self.url(self.ana)).status_code, 403)

    def test_admin_y_encargado_ven_el_de_cualquiera_y_pueden_buscar(self):
        for cuenta in (self.admin, self.encargado):
            self.client.force_login(cuenta)
            self.assertEqual(self.client.get(self.url(self.diego)).status_code, 200)
            r = self.client.get(reverse("reportes:historial_personas"), {"q": self.ana.dni})
            self.assertEqual([p.id for p in r.context["resultados"]], [self.ana.pk])

    def test_persona_inexistente_da_404(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("reportes:historial_persona", args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)


class HistorialItemTests(DatosDeHistorialMixin, TestCase):
    def test_trae_quien_se_lo_presto_con_nombre_dni_y_estado(self):
        datos = historial_servicio().de_item(self.laptop.id)
        self.assertEqual(dict(datos.resumen)["Préstamos"], 2)
        self.assertEqual(dict(datos.resumen)["Estado actual"], self.laptop.estado_display)
        prestamos = datos.secciones[0]
        self.assertEqual([f[3] for f in prestamos.filas], ["Ana Alumna", "Ana Alumna"])
        self.assertEqual(prestamos.filas[0][4], self.ana.dni)

    def test_muestra_las_perdidas_del_item(self):
        eventos = historial_servicio().de_item(self.camara.id).secciones[1]
        self.assertEqual(eventos.filas[0][1:4], ["Pérdida", "Diego Docente", self.diego.dni])

    def test_solo_admin_y_encargado(self):
        url = reverse("reportes:historial_item", args=[self.laptop.id])
        for cuenta, esperado in ((self.ana, 403), (self.supervisor, 403),
                                 (self.encargado, 200), (self.admin, 200)):
            self.client.force_login(cuenta)
            self.assertEqual(self.client.get(url).status_code, esperado, cuenta.nombres)
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("reportes:historial_items")).status_code, 403)

    def test_buscar_item_por_codigo(self):
        self.client.force_login(self.encargado)
        r = self.client.get(reverse("reportes:historial_items"), {"q": "EQP-901"})
        self.assertEqual([i.id for i in r.context["resultados"]], [self.laptop.id])


class DescargaHistorialTests(DatosDeHistorialMixin, TestCase):
    def test_persona_en_excel_y_pdf_deja_constancia(self):
        self.client.force_login(self.ana)
        for formato, tipo in (("excel", "spreadsheetml"), ("pdf", "pdf")):
            r = self.client.get(reverse("reportes:exportar_historial_persona", args=[self.ana.pk, formato]))
            self.assertEqual(r.status_code, 200)
            self.assertIn(tipo, r["Content-Type"])
            self.assertIn(self.ana.dni, r["Content-Disposition"])
        self.assertEqual(RegistroAuditoria.objects.filter(
            accion=TipoAccion.EXPORTACION_REPORTE, entidad="Cuenta", entidad_id=self.ana.pk).count(), 2)
        # No puede descargar el de otra persona.
        r = self.client.get(reverse("reportes:exportar_historial_persona", args=[self.diego.pk, "pdf"]))
        self.assertEqual(r.status_code, 403)

    def test_el_excel_trae_las_tres_secciones(self):
        contenido, _, _ = historial_servicio().exportar_persona(self.ana.pk, "excel")
        textos = [c for fila in load_workbook(io.BytesIO(contenido)).active.iter_rows(values_only=True)
                  for c in fila if c]
        for seccion in ("Préstamos", "Sanciones", "Pérdidas", "No tiene casos de pérdida."):
            self.assertIn(seccion, textos)

    def test_item_solo_para_el_personal(self):
        url = reverse("reportes:exportar_historial_item", args=[self.laptop.id, "excel"])
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.encargado)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("EQP-901", r["Content-Disposition"])
