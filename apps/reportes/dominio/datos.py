"""Resultado de un reporte, independiente de cómo se muestre (pantalla, Excel o PDF).

Las celdas guardan su valor REAL (int, Decimal, date, datetime, Porcentaje, Soles...)
y no texto: así el Excel recibe números que se pueden sumar y graficar, y cada salida
les da formato a su manera. `como_texto()` es el formato común para la pantalla y el PDF.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from django.utils import timezone

AVISO_DATOS_PERSONALES = (
    "Contiene datos personales (Ley N.° 29733). Uso interno de la Escuela: no difundir."
)


class ReporteNoDisponible(Exception):
    """El tipo de reporte necesita datos de otro módulo que aún no se conecta."""


@dataclass(frozen=True)
class Porcentaje:
    """Una fracción entre 0 y 1 (None si no hay con qué calcularla)."""
    fraccion: Optional[float]


@dataclass(frozen=True)
class Soles:
    monto: Decimal


@dataclass
class Grafico:
    """Datos para dibujar un gráfico simple: barras ('bar') o dona ('doughnut')."""
    tipo: str
    titulo: str
    etiquetas: list
    valores: list


@dataclass
class Seccion:
    """Una tabla con título dentro de un historial (préstamos, sanciones, pérdidas...)."""
    titulo: str
    columnas: list
    filas: list = field(default_factory=list)
    vacio: str = "Sin registros."

    @property
    def filas_texto(self):
        return [[como_texto(v) for v in fila] for fila in self.filas]


@dataclass
class DatosReporte:
    titulo: str
    subtitulo: str
    resumen: list = field(default_factory=list)   # [(etiqueta, valor), ...]
    columnas: list = field(default_factory=list)
    filas: list = field(default_factory=list)     # lista de listas de valores
    grafico: Optional[Grafico] = None
    total_filas: Optional[int] = None   # filas que habría sin recortar (rankings)
    generado_por: str = ""
    generado_en: Optional[datetime] = None
    secciones: list = field(default_factory=list)   # historiales: varias tablas con título

    @property
    def sello(self):
        """'Generado el 18/11/2026 10:30 por Ana Pérez' (para la pantalla y los archivos)."""
        partes = []
        if self.generado_en:
            partes.append(f"Generado el {como_texto(self.generado_en)}")
        if self.generado_por:
            partes.append(f"por {self.generado_por}")
        return " ".join(partes)

    @property
    def recortado(self):
        """True si la pantalla muestra solo el top y la descarga trae más filas."""
        return self.total_filas is not None and self.total_filas > len(self.filas)

    @property
    def resumen_texto(self):
        return [(etiqueta, como_texto(valor)) for etiqueta, valor in self.resumen]

    @property
    def filas_texto(self):
        return [[como_texto(v) for v in fila] for fila in self.filas]


def como_texto(valor):
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, Porcentaje):
        return "—" if valor.fraccion is None else f"{valor.fraccion * 100:.1f} %"
    if isinstance(valor, Soles):
        return f"S/ {valor.monto:,.2f}"
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor)
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)
