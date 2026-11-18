"""Cálculo de los datos de cada reporte (solo consulta, nunca modifica otros módulos).

Las celdas llevan su valor real (int, date, datetime, Porcentaje, Soles); el formato lo
pone cada salida (pantalla, Excel o PDF). Ver dominio/datos.py.
"""
from collections import Counter
from decimal import Decimal

from django.utils import timezone

from apps.auditoria.models import TipoAccion
from apps.common.choices import EstadoPrestamo
from apps.reportes.dominio.datos import (
    DatosReporte, Grafico, Porcentaje, ReporteNoDisponible, Soles,
)
from apps.reportes.dominio.exportador import CONTENT_TYPES, EXTENSIONES, FORMATOS
from apps.reportes.dominio.models import TipoReporte
from apps.sanciones.models import TipoSancion
from apps.sanciones.servicios import estado_de

TOP = 15              # filas de los rankings EN PANTALLA (la descarga trae la lista completa)
TOP_GRAFICO = 10      # barras del gráfico

# Reportes que se calculan solo con datos de Sanciones y Pérdidas.
TIPOS_BASICOS = {
    TipoReporte.SANCIONES_POR_PERIODO,
    TipoReporte.ITEMS_PERDIDOS_DANIADOS,
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _periodo(reporte):
    return f"Periodo: {reporte.periodo_inicio:%d/%m/%Y} al {reporte.periodo_fin:%d/%m/%Y}"


def _alcance(limite, que):
    return f" · los {limite} {que}" if limite else " · lista completa"


def _corto(uuid_):
    return str(uuid_)[:8]


def _duracion(delta):
    minutos = int(delta.total_seconds() // 60)
    dias, resto = divmod(minutos, 1440)
    horas, mins = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {mins} min"
    return f"{mins} min"


def _clasificar(p, ahora):
    """'a_tiempo' | 'con_atraso' | 'en_curso' | 'perdido' para un préstamo."""
    if p.estado == EstadoPrestamo.CERRADO_POR_PERDIDA:
        return "perdido"
    if p.estado == EstadoPrestamo.DEVUELTO and p.fecha_devolucion_real:
        return "a_tiempo" if p.fecha_devolucion_real <= p.fecha_vencimiento else "con_atraso"
    return "con_atraso" if p.fecha_vencimiento < ahora else "en_curso"


def _fraccion(parte, total):
    return Porcentaje(parte / total if total else None)


def _ranking(conteo, clave, limite):
    orden = sorted(conteo, key=clave)
    return orden[:limite] if limite else orden


# ---------------------------------------------------------------------------
# Reportes que dependen de préstamos (Circulación)
# ---------------------------------------------------------------------------
def _items_mas_prestados(reporte, prestamos, items, limite=TOP):
    conteo = Counter(p.item_id for p in prestamos)

    def datos_item(item_id):
        return items.get(item_id, (_corto(item_id), "", "—"))

    ranking = _ranking(conteo, lambda i: (-conteo[i], datos_item(i)[0]), limite)
    filas = []
    for n, item_id in enumerate(ranking, start=1):
        codigo, nombre, categoria = datos_item(item_id)
        filas.append([n, codigo, nombre, categoria, conteo[item_id]])
    top = filas[:TOP_GRAFICO]
    return DatosReporte(
        titulo="Ítems más prestados",
        subtitulo=_periodo(reporte) + _alcance(limite, "más prestados"),
        resumen=[("Préstamos en el periodo", len(prestamos)),
                 ("Ítems distintos prestados", len(conteo))],
        columnas=["N.º", "Código", "Ítem", "Categoría", "Préstamos"],
        filas=filas,
        total_filas=len(conteo),
        grafico=Grafico("bar", "Préstamos por ítem",
                        [f"{f[1]} · {f[2]}" for f in top], [f[4] for f in top]),
    )


def _usuarios_mas_activos(reporte, prestamos, nombres, ahora, limite=TOP):
    total, a_tiempo, con_atraso = Counter(), Counter(), Counter()
    for p in prestamos:
        total[p.solicitante_id] += 1
        clase = _clasificar(p, ahora)
        if clase == "a_tiempo":
            a_tiempo[p.solicitante_id] += 1
        elif clase == "con_atraso":
            con_atraso[p.solicitante_id] += 1

    def nombre(uid):
        return nombres.get(uid, _corto(uid))

    ranking = _ranking(total, lambda u: (-total[u], nombre(u)), limite)
    filas = [
        [n, nombre(u), total[u], a_tiempo[u], con_atraso[u]]
        for n, u in enumerate(ranking, start=1)
    ]
    top = filas[:TOP_GRAFICO]
    return DatosReporte(
        titulo="Usuarios más activos",
        subtitulo=_periodo(reporte) + _alcance(limite, "con más préstamos"),
        resumen=[("Préstamos en el periodo", len(prestamos)),
                 ("Solicitantes distintos", len(total))],
        columnas=["N.º", "Solicitante", "Préstamos", "Devueltos a tiempo", "Con atraso"],
        filas=filas,
        total_filas=len(total),
        grafico=Grafico("bar", "Préstamos por solicitante",
                        [f[1] for f in top], [f[2] for f in top]),
    )


def _tasa_devolucion(reporte, prestamos, nombres, items, ahora):
    """Tasa = devueltos a tiempo / (devueltos a tiempo + con atraso).

    Con atraso = devueltos después de la hora, o sin devolver con la hora ya pasada.
    No cuentan: los que siguen en curso ni los cerrados por pérdida.
    """
    filas, cuenta = [], Counter()
    for p in prestamos:
        clase = _clasificar(p, ahora)
        cuenta[clase] += 1
        if clase not in ("a_tiempo", "con_atraso"):
            continue
        if p.fecha_devolucion_real:
            if clase == "a_tiempo":
                resultado = "A tiempo"
            else:
                resultado = f"Con atraso ({_duracion(p.fecha_devolucion_real - p.fecha_vencimiento)})"
        else:
            resultado = f"Sin devolver (atrasado {_duracion(ahora - p.fecha_vencimiento)})"
        codigo = items.get(p.item_id, (_corto(p.item_id),))[0]
        filas.append([
            p.fecha_entrega, p.fecha_vencimiento, p.fecha_devolucion_real,
            nombres.get(p.solicitante_id, _corto(p.solicitante_id)), codigo, resultado,
        ])
    evaluados = cuenta["a_tiempo"] + cuenta["con_atraso"]
    return DatosReporte(
        titulo="Tasa de devolución a tiempo",
        subtitulo=_periodo(reporte) + " · préstamos entregados en el periodo",
        resumen=[
            ("Préstamos entregados", len(prestamos)),
            ("Devueltos a tiempo", cuenta["a_tiempo"]),
            ("Con atraso", cuenta["con_atraso"]),
            ("Aún en curso", cuenta["en_curso"]),
            ("Cerrados por pérdida", cuenta["perdido"]),
            ("Tasa de devolución a tiempo", _fraccion(cuenta["a_tiempo"], evaluados)),
        ],
        columnas=["Entrega", "Vencimiento", "Devolución", "Solicitante", "Ítem", "Resultado"],
        filas=filas,
        grafico=Grafico(
            "doughnut", "Resultado de los préstamos",
            ["A tiempo", "Con atraso", "En curso", "Cerrados por pérdida"],
            [cuenta["a_tiempo"], cuenta["con_atraso"], cuenta["en_curso"], cuenta["perdido"]],
        ),
    )


# ---------------------------------------------------------------------------
# Reportes de Sanciones y Pérdidas
# ---------------------------------------------------------------------------
def _sanciones_por_periodo(reporte, sanciones, nombres=None):
    nombres = nombres or {}
    por_tipo = {valor: 0 for valor, _ in TipoSancion.choices}
    vigentes = 0
    filas = []
    for s in sanciones:
        por_tipo[s.tipo] += 1
        estado = estado_de(s)
        vigentes += estado == "vigente"
        filas.append([
            s.fecha_inicio,
            nombres.get(s.solicitante_id, _corto(s.solicitante_id)),
            s.get_tipo_display(),
            s.motivo,
            s.duracion_dias if s.duracion_dias else "sin plazo",
            estado.capitalize(),
            nombres.get(s.aplicada_por_id, _corto(s.aplicada_por_id)),
        ])
    resumen = [("Total de sanciones", len(sanciones))]
    resumen += [(label, por_tipo[valor]) for valor, label in TipoSancion.choices]
    resumen.append(("Vigentes hoy", vigentes))
    return DatosReporte(
        titulo="Sanciones aplicadas por periodo",
        subtitulo=_periodo(reporte),
        resumen=resumen,
        columnas=["Fecha inicio", "Solicitante", "Tipo", "Motivo", "Duración (días)", "Estado",
                  "Aplicada por"],
        filas=filas,
        grafico=Grafico("doughnut", "Sanciones por tipo",
                        [label for _, label in TipoSancion.choices],
                        [por_tipo[valor] for valor, _ in TipoSancion.choices]),
    )


def _perdidas_por_periodo(reporte, casos, danios=(), nombres=None, items=None, item_de_prestamo=None):
    """Ítems perdidos (Gestión de Pérdidas) y dañados (auditoría ITEM_DANIADO)."""
    nombres = nombres or {}
    items = items or {}
    item_de_prestamo = item_de_prestamo or {}

    def referencia_item(item_id, respaldo):
        if item_id in items:
            codigo, nombre, _ = items[item_id]
            return f"Ítem {codigo} · {nombre}"
        return respaldo

    costo_total = sum((c.costo_estimado for c in casos if c.costo_estimado), Decimal("0"))
    filas = []
    for c in casos:
        filas.append((c.fecha, [
            c.fecha, "Pérdida",
            referencia_item(item_de_prestamo.get(c.prestamo_id), f"Préstamo {_corto(c.prestamo_id)}"),
            nombres.get(c.solicitante_id, _corto(c.solicitante_id)),
            c.observaciones or None,
            Soles(c.costo_estimado) if c.costo_estimado is not None else None,
        ]))
    for d in danios:
        dia = timezone.localtime(d.fecha).date()
        respaldo = f"{d.entidad} {_corto(d.entidad_id)}"
        referencia = referencia_item(d.entidad_id, respaldo) if d.entidad == "Item" else respaldo
        persona = nombres.get(d.solicitante_id, _corto(d.solicitante_id)) if d.solicitante_id else None
        filas.append((dia, [dia, "Daño", referencia, persona, d.motivo or None, None]))
    filas = [fila for _, fila in sorted(filas, key=lambda x: x[0])]
    resumen = [
        ("Casos de pérdida", len(casos)),
        ("Abiertos", sum(1 for c in casos if not c.cerrado)),
        ("Cerrados", sum(1 for c in casos if c.cerrado)),
        ("Ítems dañados", len(danios)),
        ("Costo estimado total", Soles(costo_total)),
    ]
    return DatosReporte(
        titulo="Ítems perdidos o dañados por periodo",
        subtitulo=_periodo(reporte),
        resumen=resumen,
        columnas=["Fecha", "Tipo", "Referencia", "Persona", "Detalle", "Costo estimado"],
        filas=filas,
        grafico=Grafico("doughnut", "Pérdidas y daños", ["Pérdidas", "Daños"], [len(casos), len(danios)]),
    )


# ---------------------------------------------------------------------------
# Servicio de aplicación
# ---------------------------------------------------------------------------
class ReporteServicioAplicacion:
    def __init__(self, repositorio, sancion_servicio, caso_perdida_servicio, exportador,
                 fuente=None, auditoria=None):
        self._repo = repositorio
        self._sanciones = sancion_servicio
        self._casos = caso_perdida_servicio
        self._exportador = exportador
        self._fuente = fuente          # IFuenteDeReportes: préstamos, daños, nombres e ítems
        self._auditoria = auditoria    # deja constancia de descargas y eliminaciones (RF-J)

    # --- registro de reportes generados ---
    # No hay "editar": un reporte es la constancia de qué se pidió, quién y cuándo.
    # Para otro periodo se genera uno nuevo.
    def listar(self):
        return self._repo.listar()

    def obtener(self, pk):
        return self._repo.obtener(pk)

    def crear(self, reporte, actor_id):
        reporte.generado_por_id = actor_id
        return self._repo.guardar(reporte)

    def eliminar(self, reporte, actor_id=None):
        if self._auditoria and actor_id:
            self._auditoria.registrar(
                actor_id, TipoAccion.ELIMINACION_REPORTE, "Reporte", reporte.pk,
                f"{reporte.get_tipo_display()} · {_periodo(reporte)}",
            )
        self._repo.eliminar(reporte)

    # --- cálculo y exportación ---
    def esta_disponible(self, tipo):
        return tipo in TIPOS_BASICOS or self._fuente is not None

    def _nombres(self, ids):
        return self._fuente.nombres_de_cuentas(ids) if self._fuente else {}

    def generar_datos(self, reporte, ahora=None, limite=TOP):
        """Calcula el reporte. `limite` recorta los rankings (None = lista completa)."""
        ahora = ahora or timezone.now()
        datos = self._calcular(reporte, ahora, limite)
        datos.generado_en = ahora
        if reporte.generado_por_id:
            datos.generado_por = self._nombres({reporte.generado_por_id}).get(
                reporte.generado_por_id, _corto(reporte.generado_por_id))
        return datos

    def _calcular(self, reporte, ahora, limite):
        inicio, fin = reporte.periodo_inicio, reporte.periodo_fin
        if reporte.tipo == TipoReporte.SANCIONES_POR_PERIODO:
            sanciones = self._sanciones.por_periodo(inicio, fin)
            ids = {s.solicitante_id for s in sanciones} | {s.aplicada_por_id for s in sanciones}
            return _sanciones_por_periodo(reporte, sanciones, self._nombres(ids))
        if reporte.tipo == TipoReporte.ITEMS_PERDIDOS_DANIADOS:
            casos = self._casos.por_periodo(inicio, fin)
            danios, items, item_de_prestamo = [], {}, {}
            if self._fuente:
                danios = self._fuente.danios_del_periodo(inicio, fin)
                item_de_prestamo = self._fuente.items_de_prestamos({c.prestamo_id for c in casos})
                ids_items = {d.entidad_id for d in danios if d.entidad == "Item"}
                ids_items |= set(item_de_prestamo.values())
                items = self._fuente.datos_de_items(ids_items) if ids_items else {}
            personas = {c.solicitante_id for c in casos} | {d.solicitante_id for d in danios if d.solicitante_id}
            return _perdidas_por_periodo(
                reporte, casos, danios, self._nombres(personas), items, item_de_prestamo,
            )
        if self._fuente is None:
            raise ReporteNoDisponible(
                f"El reporte «{reporte.get_tipo_display()}» necesita los datos de préstamos "
                "(módulo Circulación) y todavía no están conectados."
            )
        prestamos = self._fuente.prestamos_del_periodo(inicio, fin)
        if reporte.tipo == TipoReporte.ITEMS_MAS_PRESTADOS:
            items = self._fuente.datos_de_items({p.item_id for p in prestamos})
            return _items_mas_prestados(reporte, prestamos, items, limite)
        nombres = self._nombres({p.solicitante_id for p in prestamos})
        if reporte.tipo == TipoReporte.USUARIOS_MAS_ACTIVOS:
            return _usuarios_mas_activos(reporte, prestamos, nombres, ahora, limite)
        if reporte.tipo == TipoReporte.TASA_DEVOLUCION_A_TIEMPO:
            items = self._fuente.datos_de_items({p.item_id for p in prestamos})
            return _tasa_devolucion(reporte, prestamos, nombres, items, ahora)
        raise ReporteNoDisponible(f"Tipo de reporte no soportado: {reporte.tipo}")

    def exportar(self, reporte, formato, actor_id=None):
        """Devuelve (bytes, content_type, nombre). La descarga trae la lista completa.

        Lanza ReporteNoDisponible o ValueError (formato desconocido).
        """
        if formato not in FORMATOS:
            raise ValueError(f"Formato no soportado: {formato}")
        datos = self.generar_datos(reporte, limite=None)
        if actor_id:   # quien descarga, no quien lo generó
            datos.generado_por = self._nombres({actor_id}).get(actor_id, _corto(actor_id))
        contenido = self._exportador.exportar(datos, formato)
        if self._auditoria and actor_id:
            self._auditoria.registrar(
                actor_id, TipoAccion.EXPORTACION_REPORTE, "Reporte", reporte.pk,
                f"{reporte.get_tipo_display()} en {EXTENSIONES[formato].upper()} · {_periodo(reporte)}",
            )
        nombre = (
            f"reporte_{reporte.tipo.lower()}_{reporte.periodo_inicio:%Y%m%d}"
            f"_{reporte.periodo_fin:%Y%m%d}.{EXTENSIONES[formato]}"
        )
        return contenido, CONTENT_TYPES[formato], nombre
