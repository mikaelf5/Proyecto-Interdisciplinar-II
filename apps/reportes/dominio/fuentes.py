"""Puerto con los datos de OTROS contextos que necesitan los reportes.

Reportes solo consulta (nunca modifica). El dominio dice qué datos necesita;
la implementación concreta está en infraestructura/fuente_datos.py.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class FilaPrestamo:
    id: UUID
    item_id: UUID
    solicitante_id: UUID
    estado: str
    fecha_entrega: datetime
    fecha_vencimiento: datetime
    fecha_devolucion_real: Optional[datetime] = None


@dataclass(frozen=True)
class FilaDanio:
    fecha: datetime
    entidad: str
    entidad_id: UUID
    motivo: str


class IFuenteDeReportes(ABC):
    @abstractmethod
    def prestamos_del_periodo(self, inicio, fin):
        """Préstamos ENTREGADOS entre las dos fechas (inclusive) -> list[FilaPrestamo]."""

    @abstractmethod
    def danios_del_periodo(self, inicio, fin):
        """Ítems dañados registrados en el periodo -> list[FilaDanio]."""

    @abstractmethod
    def nombres_de_cuentas(self, ids):
        """{cuenta_id: nombres}"""

    @abstractmethod
    def datos_de_items(self, ids):
        """{item_id: (codigo, nombre, categoria)}"""
