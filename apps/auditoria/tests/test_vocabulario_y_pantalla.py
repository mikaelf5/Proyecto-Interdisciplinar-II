"""Auditoría: vocabulario de acciones, motivo obligatorio (RF-J1) y pantalla."""
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.auditoria.dominio.constantes import SISTEMA_ID
from apps.auditoria.dominio.models import ACCIONES_CON_MOTIVO, TipoAccion
from apps.auditoria.fabrica import auditoria_servicio
from apps.common.choices import RolSistema
from apps.sanciones.tests.helpers import crear_cuenta


class VocabularioTests(SimpleTestCase):
    def test_todas_las_acciones_que_usa_el_codigo_existen_en_TipoAccion(self):
        """Si alguien auditara con un nombre que no está en TipoAccion, esta prueba falla."""
        raiz = Path(settings.BASE_DIR) / "apps"
        usadas = {}
        patrones = [
            r'accion\s*=\s*"([A-Z_]{4,})"',            # accion="ENTREGA_PRESTAMO"
            r'_auditar\(\s*"([A-Z_]{4,})"',            # self._auditar("CAMBIO_ESTADO", ...)
            r'TipoAccion\.([A-Z_]{4,})',               # TipoAccion.SANCION
        ]
        for archivo in raiz.rglob("*.py"):
            ruta = str(archivo)
            if "/tests/" in ruta or "/migrations/" in ruta or archivo.name.startswith("tests"):
                continue
            texto = archivo.read_text(encoding="utf-8")
            for patron in patrones:
                for nombre in re.findall(patron, texto):
                    usadas.setdefault(nombre, ruta)
        validas = set(TipoAccion.values)
        desconocidas = {n: f for n, f in usadas.items() if n not in validas}
        self.assertEqual(desconocidas, {}, "Acciones de auditoría que no están en TipoAccion")
        self.assertGreaterEqual(len(usadas), 8)          # sí encontró las del proyecto

    def test_las_acciones_de_circulacion_estan_en_el_vocabulario(self):
        for accion in ("ENTREGA_PRESTAMO", "RENOVACION_PRESTAMO", "DEVOLUCION_PRESTAMO"):
            self.assertIn(accion, TipoAccion.values)


class MotivoObligatorioTests(TestCase):
    def test_las_acciones_sensibles_exigen_motivo(self):
        for accion in ACCIONES_CON_MOTIVO:
            for vacio in ("", "   ", None):
                with self.assertRaises(ValidationError, msg=(accion, vacio)):
                    auditoria_servicio().registrar(uuid.uuid4(), accion, "X", uuid.uuid4(), vacio)

    def test_con_motivo_se_guardan_y_las_demas_no_lo_exigen(self):
        s = auditoria_servicio()
        s.registrar(uuid.uuid4(), TipoAccion.SANCION, "Sancion", uuid.uuid4(), "Retraso reiterado")
        s.registrar(uuid.uuid4(), TipoAccion.CAMBIO_ESTADO, "Item", uuid.uuid4())      # sin motivo: permitido
        s.registrar(uuid.uuid4(), TipoAccion.ENTREGA_PRESTAMO, "Prestamo", uuid.uuid4(), "")
        self.assertEqual(len(list(s.buscar({}))), 3)

    def test_si_falta_el_motivo_no_se_guarda_nada(self):
        with self.assertRaises(ValidationError):
            auditoria_servicio().registrar(uuid.uuid4(), TipoAccion.ITEM_DANIADO, "Item", uuid.uuid4(), "")
        self.assertEqual(len(list(auditoria_servicio().buscar({}))), 0)


class NombresDeActoresTests(TestCase):
    def test_sistema_persona_y_desconocido(self):
        ana = crear_cuenta(nombres="Ana Alumna")
        desconocido = uuid.uuid4()
        nombres = auditoria_servicio().nombres_de_actores(
            {ana.pk, SISTEMA_ID, uuid.UUID(int=0), desconocido})
        self.assertEqual(nombres[ana.pk], "Ana Alumna")
        self.assertEqual(nombres[SISTEMA_ID], "Sistema (automático)")
        self.assertEqual(nombres[uuid.UUID(int=0)], "Sistema (automático)")   # el de Identidad
        self.assertEqual(nombres[desconocido], "")


class PantallaTests(TestCase):
    def setUp(self):
        self.admin = crear_cuenta(nombres="Admin Demo", roles=[RolSistema.ADMINISTRADOR])
        self.client.force_login(self.admin)
        s = auditoria_servicio()
        s.registrar(self.admin.pk, TipoAccion.SANCION, "Sancion", uuid.uuid4(), "Retraso en la devolución")
        s.registrar(SISTEMA_ID, TipoAccion.CAMBIO_ESTADO, "Prestamo", uuid.uuid4(), "Marcado como vencido")
        s.registrar(self.admin.pk, TipoAccion.ENTREGA_PRESTAMO, "Prestamo", uuid.uuid4(), "Entrega")
        self.url = reverse("auditoria:lista")

    def test_muestra_el_nombre_de_quien_hizo_la_accion(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Admin Demo")
        self.assertContains(r, "Sistema (automático)")

    def test_las_acciones_de_circulacion_se_ven_con_nombre_y_se_pueden_filtrar(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Entrega de préstamo")
        self.assertContains(r, 'value="ENTREGA_PRESTAMO"')                       # está en el desplegable
        filtrado = self.client.get(self.url, {"accion": "ENTREGA_PRESTAMO"})
        self.assertEqual(len(filtrado.context["registros"]), 1)

    def test_busqueda_en_el_motivo_y_demas_filtros(self):
        n = lambda **p: len(self.client.get(self.url, p).context["registros"])
        self.assertEqual(n(), 3)
        self.assertEqual(n(q="vencido"), 1)
        self.assertEqual(n(q="RETRASO"), 1)              # sin distinguir mayúsculas
        self.assertEqual(n(entidad="Prestamo"), 2)
        self.assertEqual(n(actor=str(self.admin.pk)[:8]), 2)
        self.assertEqual(n(accion="SANCION", q="retraso"), 1)
        self.assertEqual(n(q="no existe"), 0)

    def test_el_desplegable_de_entidades_sale_del_servicio(self):
        self.assertEqual(sorted(self.client.get(self.url).context["entidades"]), ["Prestamo", "Sancion"])

    def test_paginacion_conserva_los_filtros(self):
        s = auditoria_servicio()
        for i in range(30):
            s.registrar(self.admin.pk, TipoAccion.CAMBIO_ESTADO, "Item", uuid.uuid4(), f"cambio {i}")
        r = self.client.get(self.url, {"entidad": "Item"})
        self.assertEqual(len(r.context["registros"]), 25)
        self.assertContains(r, "entidad=Item&page=2")
