import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.auditoria.fabrica import auditoria_servicio
from apps.auditoria.models import TipoAccion
from apps.common.choices import EstadoPrestamo, RolSistema
from apps.perdidas.dominio.models import CasoPerdida
from apps.reportes.dominio.datos import Porcentaje, ReporteNoDisponible
from apps.reportes.dominio.models import Reporte, TipoReporte
from apps.reportes.fabrica import reporte_servicio
from apps.sanciones.dominio.models import Sancion
from apps.sanciones.tests.helpers import crear_cuenta, crear_item, crear_prestamo

AHORA = timezone.now()
H = lambda horas: timedelta(hours=horas)


def reporte(tipo, dias_atras=30):
    return Reporte.objects.create(
        tipo=tipo, generado_por_id=uuid.uuid4(),
        periodo_inicio=date.today() - timedelta(days=dias_atras), periodo_fin=date.today())


def valor(datos, etiqueta):
    return dict(datos.resumen)[etiqueta]


class DatosDePrestamosMixin:
    """3 ítems, 2 solicitantes y 7 préstamos con todos los resultados posibles."""

    def crear_datos(self):
        self.ana = crear_cuenta(nombres="Ana Alumna", roles=[RolSistema.SOLICITANTE])
        self.diego = crear_cuenta(nombres="Diego Docente", roles=[RolSistema.SOLICITANTE])
        self.laptop = crear_item("EQP-001", "Laptop")
        self.libro = crear_item("LIB-001", "Clean Code")
        self.balon = crear_item("DEP-001", "Balón")
        e = AHORA - H(10)
        # Laptop: 3 préstamos (a tiempo, con atraso, perdido)
        crear_prestamo(self.laptop.id, self.ana.pk, EstadoPrestamo.DEVUELTO, e, e + H(4), e + H(3))
        crear_prestamo(self.laptop.id, self.ana.pk, EstadoPrestamo.DEVUELTO, e, e + H(4), e + H(6))
        self.prestamo_perdido = crear_prestamo(
            self.laptop.id, self.diego.pk, EstadoPrestamo.CERRADO_POR_PERDIDA, e, e + H(4))
        # Libro: 2 préstamos (a tiempo, sin devolver y con la hora pasada)
        crear_prestamo(self.libro.id, self.diego.pk, EstadoPrestamo.DEVUELTO, e, e + H(5), e + H(1))
        crear_prestamo(self.libro.id, self.diego.pk, EstadoPrestamo.VENCIDO, e, e + H(2))
        # Balón: 1 en curso (vence en el futuro)
        crear_prestamo(self.balon.id, self.ana.pk, EstadoPrestamo.ACTIVO, AHORA - H(1), AHORA + H(3))
        # Fuera del periodo (hace 100 días): no debe contarse
        crear_prestamo(self.balon.id, self.ana.pk, EstadoPrestamo.DEVUELTO, AHORA - timedelta(days=100),
                       AHORA - timedelta(days=100) + H(4), AHORA - timedelta(days=100) + H(2))


class ReportesDePrestamosTests(DatosDePrestamosMixin, TestCase):
    def setUp(self):
        self.crear_datos()
        self.servicio = reporte_servicio()

    def test_items_mas_prestados(self):
        d = self.servicio.generar_datos(reporte(TipoReporte.ITEMS_MAS_PRESTADOS))
        self.assertEqual(valor(d, "Préstamos en el periodo"), 6)        # el de hace 100 días no cuenta
        self.assertEqual(valor(d, "Ítems distintos prestados"), 3)
        self.assertEqual(d.filas[0], [1, "EQP-001", "Laptop", self.laptop.categoria_nombre, 3])
        self.assertEqual([f[1] for f in d.filas], ["EQP-001", "LIB-001", "DEP-001"])
        self.assertEqual([f[4] for f in d.filas], [3, 2, 1])

    def test_usuarios_mas_activos(self):
        d = self.servicio.generar_datos(reporte(TipoReporte.USUARIOS_MAS_ACTIVOS))
        # Diego: 3 (libro a tiempo, libro sin devolver atrasado, laptop perdida) | Ana: 3 (a tiempo, tarde, en curso)
        self.assertEqual(valor(d, "Solicitantes distintos"), 2)
        por_nombre = {f[1]: f for f in d.filas}
        self.assertEqual(por_nombre["Ana Alumna"][2:], [3, 1, 1])    # préstamos, a tiempo, con atraso
        self.assertEqual(por_nombre["Diego Docente"][2:], [3, 1, 1])
        self.assertEqual([f[1] for f in d.filas], ["Ana Alumna", "Diego Docente"])   # empate: por nombre

    def test_tasa_de_devolucion_a_tiempo(self):
        d = self.servicio.generar_datos(reporte(TipoReporte.TASA_DEVOLUCION_A_TIEMPO))
        self.assertEqual(valor(d, "Préstamos entregados"), 6)
        self.assertEqual(valor(d, "Devueltos a tiempo"), 2)       # laptop + libro
        self.assertEqual(valor(d, "Con atraso"), 2)               # laptop tarde + libro sin devolver vencido
        self.assertEqual(valor(d, "Aún en curso"), 1)
        self.assertEqual(valor(d, "Cerrados por pérdida"), 1)
        self.assertEqual(valor(d, "Tasa de devolución a tiempo"), Porcentaje(0.5))
        self.assertEqual(dict(d.resumen_texto)["Tasa de devolución a tiempo"], "50.0 %")
        resultados = sorted(f[5].split(" (")[0] for f in d.filas)
        self.assertEqual(resultados, ["A tiempo", "A tiempo", "Con atraso", "Sin devolver"])
        self.assertTrue(any("Con atraso (2 h" in f[5] for f in d.filas))

    def test_tasa_sin_datos(self):
        vacio = Reporte(tipo=TipoReporte.TASA_DEVOLUCION_A_TIEMPO,
                        periodo_inicio=date(2000, 1, 1), periodo_fin=date(2000, 1, 2))
        d = self.servicio.generar_datos(vacio)
        self.assertEqual(dict(d.resumen_texto)["Tasa de devolución a tiempo"], "—")
        self.assertEqual(d.filas, [])

    def test_perdidos_y_daniados(self):
        caso = CasoPerdida.objects.create(prestamo_id=self.prestamo_perdido.id, solicitante_id=self.diego.pk,
                                          fecha=date.today(), observaciones="Se perdió", costo_estimado=3500)
        aud = auditoria_servicio()
        aud.registrar(uuid.uuid4(), TipoAccion.ITEM_DANIADO, "Item", self.libro.id, "Páginas rotas")
        aud.registrar(uuid.uuid4(), TipoAccion.ITEM_DANIADO, "CasoPerdida", caso.pk, "ya sale como pérdida")
        d = self.servicio.generar_datos(reporte(TipoReporte.ITEMS_PERDIDOS_DANIADOS))
        self.assertEqual(valor(d, "Casos de pérdida"), 1)
        self.assertEqual(valor(d, "Ítems dañados"), 1)           # el de CasoPerdida no se cuenta dos veces
        self.assertEqual(dict(d.resumen_texto)["Costo estimado total"], "S/ 3,500.00")
        self.assertEqual(sorted(f[1] for f in d.filas), ["Daño", "Pérdida"])
        perdida = next(f for f in d.filas if f[1] == "Pérdida")
        self.assertEqual(perdida[3], "Diego Docente")              # nombre y no UUID
        self.assertEqual(perdida[2], "Ítem EQP-001 · Laptop")       # qué ítem se perdió

    def test_sanciones_por_periodo(self):
        Sancion.objects.create(solicitante_id=self.ana.pk, aplicada_por_id=uuid.uuid4(), tipo="BANEO",
                               motivo="Robo", fecha_inicio=date.today())
        d = self.servicio.generar_datos(reporte(TipoReporte.SANCIONES_POR_PERIODO))
        self.assertEqual(valor(d, "Total de sanciones"), 1)
        self.assertEqual(valor(d, "Vigentes hoy"), 1)
        self.assertEqual(d.filas[0][1], "Ana Alumna")              # nombre y no UUID

    def test_los_5_tipos_se_exportan_a_excel_y_pdf(self):
        for tipo in TipoReporte.values:
            rep = reporte(tipo)
            self.assertTrue(self.servicio.esta_disponible(tipo), tipo)
            excel, ct, nombre = self.servicio.exportar(rep, "excel")
            self.assertTrue(nombre.endswith(".xlsx"))
            ws = load_workbook(io.BytesIO(excel)).active
            self.assertTrue(ws["A1"].value, tipo)
            pdf, ct, nombre = self.servicio.exportar(rep, "pdf")
            self.assertTrue(pdf.startswith(b"%PDF"), tipo)

    def test_excel_de_items_mas_prestados_trae_los_datos(self):
        excel, _, _ = self.servicio.exportar(reporte(TipoReporte.ITEMS_MAS_PRESTADOS), "excel")
        valores = [c.value for fila in load_workbook(io.BytesIO(excel)).active.iter_rows() for c in fila]
        for esperado in ("Ítems más prestados", "EQP-001", "Laptop", "LIB-001"):
            self.assertIn(esperado, valores)


class SinFuenteTests(TestCase):
    def test_sin_datos_de_prestamos_los_reportes_dependientes_avisan(self):
        from apps.perdidas.fabrica import caso_perdida_servicio
        from apps.reportes.aplicacion.servicios import ReporteServicioAplicacion
        from apps.reportes.infraestructura.exportador_excel_pdf import ExportadorExcelPDF
        from apps.reportes.infraestructura.repositorio_django import ReporteRepositorioImpl
        from apps.sanciones.fabrica import sancion_servicio
        s = ReporteServicioAplicacion(ReporteRepositorioImpl(), sancion_servicio(),
                                      caso_perdida_servicio(), ExportadorExcelPDF())
        self.assertTrue(s.esta_disponible(TipoReporte.SANCIONES_POR_PERIODO))
        self.assertFalse(s.esta_disponible(TipoReporte.ITEMS_MAS_PRESTADOS))
        with self.assertRaises(ReporteNoDisponible):
            s.generar_datos(reporte(TipoReporte.ITEMS_MAS_PRESTADOS))


class VistasReporteTests(DatosDePrestamosMixin, TestCase):
    def test_solo_administrador(self):
        rep = reporte(TipoReporte.ITEMS_MAS_PRESTADOS)
        urls = [reverse("reportes:lista"), reverse("reportes:detalle", args=[rep.pk]),
                reverse("reportes:exportar", args=[rep.pk, "pdf"])]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 302, u)           # sin sesión
        for rol in (RolSistema.SOLICITANTE, RolSistema.ENCARGADO, RolSistema.SUPERVISOR):
            self.client.force_login(crear_cuenta(roles=[rol]))
            for u in urls:
                self.assertEqual(self.client.get(u).status_code, 403, (rol, u))
        self.client.force_login(crear_cuenta(roles=[RolSistema.ADMINISTRADOR]))
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200, u)

    def test_detalle_muestra_la_tabla(self):
        self.crear_datos()
        self.client.force_login(crear_cuenta())
        rep = reporte(TipoReporte.ITEMS_MAS_PRESTADOS)
        r = self.client.get(reverse("reportes:detalle", args=[rep.pk]))
        self.assertContains(r, "EQP-001")
        self.assertContains(r, "Descargar Excel")

    def test_crear_reporte_guarda_quien_lo_genero(self):
        admin = crear_cuenta()
        self.client.force_login(admin)
        self.client.post(reverse("reportes:crear"), dict(
            tipo="USUARIOS_MAS_ACTIVOS",
            periodo_inicio=(date.today() - timedelta(days=7)).isoformat(),
            periodo_fin=date.today().isoformat()))
        self.assertEqual(Reporte.objects.get().generado_por_id, admin.pk)


# ---------------------------------------------------------------------------
# Revisión del 18/11/2026 (H1–H10)
# ---------------------------------------------------------------------------
class ExportadorTests(TestCase):
    """H1, H2 y H3: el PDF no pierde texto, el Excel trae números y ambos llevan sello."""

    def datos(self, motivo="ok"):
        from apps.reportes.dominio.datos import DatosReporte, Soles
        return DatosReporte(
            titulo="Prueba", subtitulo="Periodo",
            resumen=[("Total", 12), ("Tasa", Porcentaje(0.853)), ("Costo", Soles(Decimal("150.5")))],
            columnas=["Fecha", "Motivo", "Préstamos"],
            filas=[[date(2026, 11, 3), motivo, 7]],
            generado_por="Ana Admin", generado_en=AHORA,
        )

    def test_pdf_no_interpreta_el_texto_como_etiquetas(self):
        from reportlab.lib.styles import getSampleStyleSheet
        from apps.reportes.infraestructura.exportador_excel_pdf import _p, a_pdf
        estilo = getSampleStyleSheet()["Normal"]
        for texto in ("Cable <roto> por alumno", "usa <b>negrita", "A & B", "3 < 5 > 2"):
            self.assertEqual(_p(texto, estilo).getPlainText(), texto)      # no se pierde nada
            self.assertTrue(a_pdf(self.datos(texto)).startswith(b"%PDF"))   # y no se cae

    def test_excel_guarda_numeros_fechas_y_porcentajes_con_su_tipo(self):
        from apps.reportes.infraestructura.exportador_excel_pdf import a_excel
        ws = load_workbook(io.BytesIO(a_excel(self.datos()))).active
        celdas = {c.value: c for fila in ws.iter_rows() for c in fila if c.value is not None}
        self.assertIn(12, celdas)                                  # número, no "12"
        self.assertIn(7, celdas)
        tasa = next(c for c in celdas.values() if c.number_format == "0.0%")
        self.assertAlmostEqual(tasa.value, 0.853)
        self.assertIn(150.5, celdas)
        fecha = next(c for c in celdas.values() if c.number_format == "DD/MM/YYYY")
        self.assertEqual(fecha.value.date(), date(2026, 11, 3))

    def test_excel_lleva_sello_y_aviso_de_datos_personales(self):
        from apps.reportes.dominio.datos import AVISO_DATOS_PERSONALES
        from apps.reportes.infraestructura.exportador_excel_pdf import a_excel
        ws = load_workbook(io.BytesIO(a_excel(self.datos()))).active
        textos = [c.value for fila in ws.iter_rows() for c in fila if isinstance(c.value, str)]
        self.assertTrue(any(t.startswith("Generado el") and "Ana Admin" in t for t in textos))
        self.assertIn(AVISO_DATOS_PERSONALES, textos)


class DatosRevisadosTests(DatosDePrestamosMixin, TestCase):
    def setUp(self):
        self.crear_datos()
        self.servicio = reporte_servicio()

    def test_la_pantalla_recorta_y_la_descarga_trae_la_lista_completa(self):   # H8
        rep = reporte(TipoReporte.ITEMS_MAS_PRESTADOS)
        recortado = self.servicio.generar_datos(rep, limite=2)
        self.assertEqual(len(recortado.filas), 2)
        self.assertTrue(recortado.recortado)
        completo = self.servicio.generar_datos(rep, limite=None)
        self.assertEqual(len(completo.filas), 3)
        self.assertFalse(completo.recortado)
        self.assertIn("lista completa", completo.subtitulo)

    def test_los_items_se_piden_en_una_sola_consulta(self):                     # H9
        from apps.reportes.infraestructura.fuente_datos import FuenteDeReportesDjango
        fuente = FuenteDeReportesDjango()
        ids = {self.laptop.id, self.libro.id, self.balon.id, uuid.uuid4()}
        with self.assertNumQueries(1):
            datos = fuente.datos_de_items(ids)
        self.assertEqual(datos[self.libro.id][:2], ("LIB-001", "Clean Code"))
        self.assertEqual(len(datos), 4)                                         # el borrado también sale

    def test_el_reporte_trae_quien_lo_genero_y_un_grafico(self):                 # H3 + gráficos
        admin = crear_cuenta(nombres="Ana Admin")
        rep = Reporte.objects.create(tipo=TipoReporte.TASA_DEVOLUCION_A_TIEMPO, generado_por_id=admin.pk,
                                     periodo_inicio=date.today() - timedelta(days=30),
                                     periodo_fin=date.today())
        d = self.servicio.generar_datos(rep)
        self.assertEqual(d.generado_por, "Ana Admin")
        self.assertIsNotNone(d.generado_en)
        self.assertEqual(d.grafico.tipo, "doughnut")
        self.assertEqual(d.grafico.valores, [2, 2, 1, 1])


class VistasRevisadasTests(DatosDePrestamosMixin, TestCase):
    def setUp(self):
        self.admin = crear_cuenta(nombres="Ana Admin")
        self.client.force_login(self.admin)

    def test_ya_no_se_puede_editar_un_reporte(self):                            # H6
        from django.urls import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse("reportes:editar", args=[uuid.uuid4()])

    def test_descargar_deja_constancia_en_la_auditoria(self):                    # H7
        rep = reporte(TipoReporte.SANCIONES_POR_PERIODO)
        r = self.client.get(reverse("reportes:exportar", args=[rep.pk, "excel"]))
        self.assertEqual(r.status_code, 200)
        registro = auditoria_servicio().buscar({"accion": "EXPORTACION_REPORTE"})[0]
        self.assertEqual((registro.actor_id, registro.entidad, registro.entidad_id),
                         (self.admin.pk, "Reporte", rep.pk))
        self.assertIn("XLSX", registro.motivo)

    def test_eliminar_deja_constancia_en_la_auditoria(self):                     # H7
        rep = reporte(TipoReporte.SANCIONES_POR_PERIODO)
        self.client.post(reverse("reportes:eliminar", args=[rep.pk]))
        self.assertFalse(Reporte.objects.filter(pk=rep.pk).exists())
        registro = auditoria_servicio().buscar({"accion": "ELIMINACION_REPORTE"})[0]
        self.assertEqual((registro.actor_id, registro.entidad_id), (self.admin.pk, rep.pk))

    def test_el_periodo_se_valida(self):                                         # H10
        hoy = date.today()
        casos = [
            (hoy + timedelta(days=1), hoy + timedelta(days=2), "periodo_inicio"),    # futuro
            (hoy - timedelta(days=5), hoy + timedelta(days=1), "periodo_fin"),       # termina mañana
            (hoy - timedelta(days=1), hoy - timedelta(days=5), "periodo_fin"),       # al revés
            (hoy - timedelta(days=400), hoy, "periodo_fin"),                         # más de un año
        ]
        for inicio, fin, campo in casos:
            r = self.client.post(reverse("reportes:crear"), dict(
                tipo="SANCIONES_POR_PERIODO", periodo_inicio=inicio.isoformat(), periodo_fin=fin.isoformat()))
            self.assertEqual(r.status_code, 200, (inicio, fin))          # vuelve al formulario
            self.assertIn(campo, r.context["form"].errors, (inicio, fin))
        self.assertFalse(Reporte.objects.exists())

    def test_detalle_dibuja_el_grafico(self):
        self.crear_datos()
        self.client.post(reverse("reportes:crear"), dict(
            tipo="ITEMS_MAS_PRESTADOS", periodo_inicio=(date.today() - timedelta(days=30)).isoformat(),
            periodo_fin=date.today().isoformat()))
        rep = Reporte.objects.get()
        r = self.client.get(reverse("reportes:detalle", args=[rep.pk]))
        self.assertContains(r, 'id="grafico-reporte"')
        self.assertContains(r, 'id="datos-grafico"')
        self.assertContains(r, "Pedido por Ana Admin")


class QuienDevolvioDaniadoTests(DatosDePrestamosMixin, TestCase):
    """Idea de Micaela: si el daño se registró al recibir la devolución, se dice quién lo devolvió."""

    def setUp(self):
        self.crear_datos()

    def registrar_danio(self, item_id, cuando, motivo):
        from apps.auditoria.dominio.models import RegistroAuditoria
        r = auditoria_servicio().registrar(uuid.uuid4(), TipoAccion.ITEM_DANIADO, "Item", item_id, motivo)
        RegistroAuditoria.objects.filter(pk=r.pk).update(fecha_hora=cuando)

    def test_danio_al_devolver_muestra_quien_lo_devolvio_y_el_marcado_a_mano_no(self):
        e = AHORA - H(10)
        # El libro lo devolvió Diego en e + 1h; el daño se registró 2 min después.
        self.registrar_danio(self.libro.id, e + H(1) + timedelta(minutes=2), "Tapa rota")
        # Al balón nadie lo devolvió cerca de esa hora: se marcó a mano desde el catálogo.
        self.registrar_danio(self.balon.id, AHORA - H(5), "Costura abierta")
        d = reporte_servicio().generar_datos(reporte(TipoReporte.ITEMS_PERDIDOS_DANIADOS))
        danios = {f[4]: f for f in d.filas if f[1] == "Daño"}
        self.assertEqual(danios["Tapa rota"][3], "Diego Docente")
        self.assertIsNone(danios["Costura abierta"][3])

    def test_se_resuelve_con_una_consulta_para_todos_los_danios(self):
        from apps.reportes.infraestructura.fuente_datos import FuenteDeReportesDjango
        e = AHORA - H(10)
        for minutos in (1, 2, 3):
            self.registrar_danio(self.libro.id, e + H(1) + timedelta(minutes=minutos), f"daño {minutos}")
        fuente = FuenteDeReportesDjango()
        with self.assertNumQueries(2):   # 1 de auditoría + 1 de devoluciones
            filas = fuente.danios_del_periodo(date.today() - timedelta(days=1), date.today())
        self.assertEqual({f.solicitante_id for f in filas}, {self.diego.pk})
