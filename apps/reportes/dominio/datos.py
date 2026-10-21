from dataclasses import dataclass, field


class ReporteNoDisponible(Exception):
    """El tipo de reporte necesita datos de otro módulo que aún no se conecta."""


@dataclass
class DatosReporte:
    titulo: str
    subtitulo: str
    resumen: list = field(default_factory=list)   # [(etiqueta, valor), ...]
    columnas: list = field(default_factory=list)
    filas: list = field(default_factory=list)     # lista de listas de str