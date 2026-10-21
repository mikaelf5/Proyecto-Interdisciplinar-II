"""Cálculo de los datos de cada reporte (solo consulta, nunca modifica)."""
from dataclasses import dataclass, field
from decimal import Decimal

from apps.sanciones.models import TipoSancion
from apps.sanciones.servicios import estado_de


from apps.reportes.dominio.datos import DatosReporte, ReporteNoDisponible
from apps.reportes.dominio.exportador import CONTENT_TYPES, EXTENSIONES, FORMATOS
from apps.reportes.dominio.models import TipoReporte


# Tipos que ya se pueden calcular con los datos de este equipo de módulos.
# Los demás dependen de Circulación (préstamos) y se habilitan al integrarlo.
TIPOS_DISPONIBLES = {
    TipoReporte.SANCIONES_POR_PERIODO,
    TipoReporte.ITEMS_PERDIDOS_DANIADOS,
}



def _periodo(reporte):
    return f"Periodo: {reporte.periodo_inicio:%d/%m/%Y} al {reporte.periodo_fin:%d/%m/%Y}"




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


def _perdidas_por_periodo(reporte, casos):
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


class ReporteServicioAplicacion:
    def __init__(self, repositorio, sancion_servicio, caso_perdida_servicio, exportador):
        self._repo = repositorio
        self._sanciones = sancion_servicio
        self._casos = caso_perdida_servicio
        self._exportador = exportador

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
        return tipo in TIPOS_DISPONIBLES

    def generar_datos(self, reporte):
        inicio, fin = reporte.periodo_inicio, reporte.periodo_fin
        if reporte.tipo == TipoReporte.SANCIONES_POR_PERIODO:
            return _sanciones_por_periodo(reporte, self._sanciones.por_periodo(inicio, fin))
        if reporte.tipo == TipoReporte.ITEMS_PERDIDOS_DANIADOS:
            return _perdidas_por_periodo(reporte, self._casos.por_periodo(inicio, fin))
        raise ReporteNoDisponible(
            f"El reporte «{reporte.get_tipo_display()}» necesita los datos de préstamos "
            "(módulo Circulación) y se habilitará al integrarlo."
        )

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