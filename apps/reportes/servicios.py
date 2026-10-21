"""Cálculo de los datos de cada reporte (solo consulta, nunca modifica)."""
from dataclasses import dataclass, field
from decimal import Decimal

from apps.perdidas.models import CasoPerdida
from apps.sanciones.models import Sancion, TipoSancion
from apps.sanciones.servicios import estado_de

from .models import TipoReporte

# Tipos que ya se pueden calcular con los datos de este equipo de módulos.
# Los demás dependen de Circulación (préstamos) y se habilitan al integrarlo.
TIPOS_DISPONIBLES = {
    TipoReporte.SANCIONES_POR_PERIODO,
    TipoReporte.ITEMS_PERDIDOS_DANIADOS,
}


class ReporteNoDisponible(Exception):
    """El tipo de reporte necesita datos de otro módulo que aún no se conecta."""


@dataclass
class DatosReporte:
    titulo: str
    subtitulo: str
    resumen: list = field(default_factory=list)   # [(etiqueta, valor), ...]
    columnas: list = field(default_factory=list)
    filas: list = field(default_factory=list)     # lista de listas de str


def esta_disponible(tipo):
    return tipo in TIPOS_DISPONIBLES


def _periodo(reporte):
    return f"Periodo: {reporte.periodo_inicio:%d/%m/%Y} al {reporte.periodo_fin:%d/%m/%Y}"


def generar_datos(reporte):
    if reporte.tipo == TipoReporte.SANCIONES_POR_PERIODO:
        return _sanciones_por_periodo(reporte)
    if reporte.tipo == TipoReporte.ITEMS_PERDIDOS_DANIADOS:
        return _perdidas_por_periodo(reporte)
    raise ReporteNoDisponible(
        f"El reporte «{reporte.get_tipo_display()}» necesita los datos de préstamos "
        "(módulo Circulación) y se habilitará al integrarlo."
    )


def _sanciones_por_periodo(reporte):
    sanciones = list(
        Sancion.objects.filter(
            fecha_inicio__range=(reporte.periodo_inicio, reporte.periodo_fin)
        ).order_by("fecha_inicio", "creado_en")
    )
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


def _perdidas_por_periodo(reporte):
    casos = list(
        CasoPerdida.objects.filter(
            fecha__range=(reporte.periodo_inicio, reporte.periodo_fin)
        ).order_by("fecha", "creado_en")
    )
    costo_total = sum((c.costo_estimado for c in casos if c.costo_estimado), Decimal("0"))
    filas = [
        [
            f"{c.fecha:%d/%m/%Y}",
            str(c.prestamo_id),
            str(c.solicitante_id),
            c.observaciones or "—",
            f"S/ {c.costo_estimado:.2f}" if c.costo_estimado is not None else "—",
            "Cerrado" if c.cerrado else "Abierto",
        ]
        for c in casos
    ]
    resumen = [
        ("Casos de pérdida", str(len(casos))),
        ("Abiertos", str(sum(1 for c in casos if not c.cerrado))),
        ("Cerrados", str(sum(1 for c in casos if c.cerrado))),
        ("Costo estimado total", f"S/ {costo_total:.2f}"),
    ]
    return DatosReporte(
        titulo="Ítems perdidos o dañados por periodo",
        subtitulo=_periodo(reporte) + " · incluye casos de pérdida (los daños se sumarán al integrar Catálogo)",
        resumen=resumen,
        columnas=["Fecha", "Préstamo", "Solicitante", "Observaciones", "Costo estimado", "Estado"],
        filas=filas,
    )
