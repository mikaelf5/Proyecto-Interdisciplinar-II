"""Cálculo de los datos de cada reporte (solo consulta, nunca modifica)."""
from collections import Counter
from decimal import Decimal

from django.utils import timezone

from apps.common.choices import EstadoPrestamo
from apps.reportes.dominio.datos import DatosReporte, ReporteNoDisponible
from apps.reportes.dominio.exportador import CONTENT_TYPES, EXTENSIONES, FORMATOS
from apps.reportes.dominio.models import TipoReporte
from apps.sanciones.models import TipoSancion
from apps.sanciones.servicios import estado_de

TOP = 15  # filas de los rankings

# Reportes que se calculan solo con datos de Sanciones y Pérdidas.
TIPOS_BASICOS = {
    TipoReporte.SANCIONES_POR_PERIODO,
    TipoReporte.ITEMS_PERDIDOS_DANIADOS,
}


def _periodo(reporte):
    return f"Periodo: {reporte.periodo_inicio:%d/%m/%Y} al {reporte.periodo_fin:%d/%m/%Y}"





# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _corto(uuid_):
    return str(uuid_)[:8]


def _local(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else "—"


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


def _porcentaje(parte, total):
    return f"{parte * 100 / total:.1f} %" if total else "—"


# ---------------------------------------------------------------------------
# Reportes que dependen de préstamos (Circulación)
# ---------------------------------------------------------------------------
def _items_mas_prestados(reporte, prestamos, items):
    conteo = Counter(p.item_id for p in prestamos)

    def clave(item_id):
        codigo, _, _ = items.get(item_id, (_corto(item_id), "", ""))
        return (-conteo[item_id], codigo)

    ranking = sorted(conteo, key=clave)[:TOP]
    filas = []
    for n, item_id in enumerate(ranking, start=1):
        codigo, nombre, categoria = items.get(item_id, (_corto(item_id), "", "—"))
        filas.append([str(n), codigo, nombre, categoria, str(conteo[item_id])])
    return DatosReporte(
        titulo="Ítems más prestados",
        subtitulo=_periodo(reporte) + f" · los {TOP} más prestados",
        resumen=[("Préstamos en el periodo", str(len(prestamos))),
                 ("Ítems distintos prestados", str(len(conteo)))],
        columnas=["N.º", "Código", "Ítem", "Categoría", "Préstamos"],
        filas=filas,
    )


def _usuarios_mas_activos(reporte, prestamos, nombres, ahora):
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

    ranking = sorted(total, key=lambda u: (-total[u], nombre(u)))[:TOP]
    filas = [
        [str(n), nombre(u), str(total[u]), str(a_tiempo[u]), str(con_atraso[u])]
        for n, u in enumerate(ranking, start=1)
    ]
    return DatosReporte(
        titulo="Usuarios más activos",
        subtitulo=_periodo(reporte) + f" · los {TOP} con más préstamos",
        resumen=[("Préstamos en el periodo", str(len(prestamos))),
                 ("Solicitantes distintos", str(len(total)))],
        columnas=["N.º", "Solicitante", "Préstamos", "Devueltos a tiempo", "Con atraso"],
        filas=filas,
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
            _local(p.fecha_entrega), _local(p.fecha_vencimiento), _local(p.fecha_devolucion_real),
            nombres.get(p.solicitante_id, _corto(p.solicitante_id)), codigo, resultado,
        ])
    evaluados = cuenta["a_tiempo"] + cuenta["con_atraso"]
    return DatosReporte(
        titulo="Tasa de devolución a tiempo",
        subtitulo=_periodo(reporte) + " · préstamos entregados en el periodo",
        resumen=[
            ("Préstamos entregados", str(len(prestamos))),
            ("Devueltos a tiempo", str(cuenta["a_tiempo"])),
            ("Con atraso", str(cuenta["con_atraso"])),
            ("Aún en curso", str(cuenta["en_curso"])),
            ("Cerrados por pérdida", str(cuenta["perdido"])),
            ("Tasa de devolución a tiempo", _porcentaje(cuenta["a_tiempo"], evaluados)),
        ],
        columnas=["Entrega", "Vencimiento", "Devolución", "Solicitante", "Ítem", "Resultado"],
        filas=filas,
    )


def _sanciones_por_periodo(reporte, sanciones):
    por_tipo = {valor: 0 for valor, _ in TipoSancion.choices}
    vigentes = 0
    filas = []
    for s in sanciones:
        por_tipo[s.tipo] += 1
        estado = estado_de(s)
        vigentes += estado == "vigente"
        filas.append([
            f"{s.fecha_inicio:%d/%m/%Y}",
            str(s.solicitante_id),
            s.get_tipo_display(),
            s.motivo,
            str(s.duracion_dias) if s.duracion_dias else "sin plazo",
            estado.capitalize(),
        ])
    resumen = [("Total de sanciones", str(len(sanciones)))]
    resumen += [(label, str(por_tipo[valor])) for valor, label in TipoSancion.choices]
    resumen.append(("Vigentes hoy", str(vigentes)))
    return DatosReporte(
        titulo="Sanciones aplicadas por periodo",
        subtitulo=_periodo(reporte),
        resumen=resumen,
        columnas=["Fecha inicio", "Solicitante", "Tipo", "Motivo", "Duración (días)", "Estado"],
        filas=filas,
    )


def _perdidas_por_periodo(reporte, casos, danios=(), nombres=None):
    """Ítems perdidos (Gestión de Pérdidas) y dañados (auditoría ITEM_DANIADO)."""
    nombres = nombres or {}
    costo_total = sum((c.costo_estimado for c in casos if c.costo_estimado), Decimal("0"))
    filas = []
    for c in casos:
        filas.append((c.fecha.strftime("%Y%m%d"), [
            c.fecha.strftime("%d/%m/%Y"), "Pérdida", f"Préstamo {_corto(c.prestamo_id)}",
            nombres.get(c.solicitante_id, _corto(c.solicitante_id)),
            c.observaciones or "—",
            f"S/ {c.costo_estimado:.2f}" if c.costo_estimado is not None else "—",
        ]))
    for d in danios:
        local = timezone.localtime(d.fecha)
        filas.append((local.strftime("%Y%m%d"), [
            local.strftime("%d/%m/%Y"), "Daño", f"{d.entidad} {_corto(d.entidad_id)}",
            "—", d.motivo or "—", "—",
        ]))
    filas = [fila for _, fila in sorted(filas, key=lambda x: x[0])]
    resumen = [
        ("Casos de pérdida", str(len(casos))),
        ("Abiertos", str(sum(1 for c in casos if not c.cerrado))),
        ("Cerrados", str(sum(1 for c in casos if c.cerrado))),
        ("Ítems dañados", str(len(danios))),
        ("Costo estimado total", f"S/ {costo_total:.2f}"),
    ]
    return DatosReporte(
        titulo="Ítems perdidos o dañados por periodo",
        subtitulo=_periodo(reporte),
        resumen=resumen,
        columnas=["Fecha", "Tipo", "Referencia", "Persona", "Detalle", "Costo estimado"],
        filas=filas,
    )


class ReporteServicioAplicacion:
    def __init__(self, repositorio, sancion_servicio, caso_perdida_servicio, exportador, fuente=None):
        self._repo = repositorio
        self._sanciones = sancion_servicio
        self._casos = caso_perdida_servicio
        self._exportador = exportador
        self._fuente = fuente  # IFuenteDeReportes: préstamos, daños, nombres e ítems

    # --- CRUD ---
    def listar(self):
        return self._repo.listar()

    def obtener(self, pk):
        return self._repo.obtener(pk)

    def crear(self, reporte, actor_id):
        reporte.generado_por_id = actor_id
        return self._repo.guardar(reporte)

    def actualizar(self, reporte):
        return self._repo.guardar(reporte)

    def eliminar(self, reporte):
        self._repo.eliminar(reporte)

    # --- cálculo y exportación ---
    def esta_disponible(self, tipo):
        return tipo in TIPOS_BASICOS or self._fuente is not None

    def _nombres(self, ids):
        return self._fuente.nombres_de_cuentas(ids) if self._fuente else {}

    def generar_datos(self, reporte, ahora=None):
        ahora = ahora or timezone.now()
        inicio, fin = reporte.periodo_inicio, reporte.periodo_fin
        if reporte.tipo == TipoReporte.SANCIONES_POR_PERIODO:
            return _sanciones_por_periodo(reporte, self._sanciones.por_periodo(inicio, fin))
        if reporte.tipo == TipoReporte.ITEMS_PERDIDOS_DANIADOS:
            casos = self._casos.por_periodo(inicio, fin)
            danios = self._fuente.danios_del_periodo(inicio, fin) if self._fuente else []
            return _perdidas_por_periodo(
                reporte, casos, danios, self._nombres({c.solicitante_id for c in casos})
            )
        if self._fuente is None:
            raise ReporteNoDisponible(
                f"El reporte «{reporte.get_tipo_display()}» necesita los datos de préstamos "
                "(módulo Circulación) y todavía no están conectados."
            )
        prestamos = self._fuente.prestamos_del_periodo(inicio, fin)
        if reporte.tipo == TipoReporte.ITEMS_MAS_PRESTADOS:
            items = self._fuente.datos_de_items({p.item_id for p in prestamos})
            return _items_mas_prestados(reporte, prestamos, items)
        nombres = self._nombres({p.solicitante_id for p in prestamos})
        if reporte.tipo == TipoReporte.USUARIOS_MAS_ACTIVOS:
            return _usuarios_mas_activos(reporte, prestamos, nombres, ahora)
        if reporte.tipo == TipoReporte.TASA_DEVOLUCION_A_TIEMPO:
            items = self._fuente.datos_de_items({p.item_id for p in prestamos})
            return _tasa_devolucion(reporte, prestamos, nombres, items, ahora)
        raise ReporteNoDisponible(f"Tipo de reporte no soportado: {reporte.tipo}")

    def exportar(self, reporte, formato):
        """Devuelve (bytes, content_type, nombre). Lanza ReporteNoDisponible."""
        if formato not in FORMATOS:
            raise ValueError(f"Formato no soportado: {formato}")
        datos = self.generar_datos(reporte)
        contenido = self._exportador.exportar(datos, formato)
        nombre = (
            f"reporte_{reporte.tipo.lower()}_{reporte.periodo_inicio:%Y%m%d}"
            f"_{reporte.periodo_fin:%Y%m%d}.{EXTENSIONES[formato]}"
        )
        return contenido, CONTENT_TYPES[formato], nombre
