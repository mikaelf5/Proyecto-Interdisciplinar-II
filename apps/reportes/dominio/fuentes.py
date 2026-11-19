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
    solicitante_id: Optional[UUID] = None   # quién lo devolvió dañado (None si no se sabe)


class IFuenteDeReportes(ABC):
    @abstractmethod
    def prestamos_del_periodo(self, inicio, fin):
        """Préstamos ENTREGADOS entre las dos fechas (inclusive) -> list[FilaPrestamo]."""

    @abstractmethod
    def items_de_prestamos(self, prestamo_ids):
        """{prestamo_id: item_id} (para decir qué ítem se perdió)."""

    @abstractmethod
    def danios_del_periodo(self, inicio, fin):
        """Ítems dañados registrados en el periodo -> list[FilaDanio]."""

    @abstractmethod
    def nombres_de_cuentas(self, ids):
        """{cuenta_id: nombres}"""

    @abstractmethod
    def datos_de_items(self, ids):
        """{item_id: (codigo, nombre, categoria)}"""


@dataclass(frozen=True)
class FichaPersona:
    id: UUID
    nombres: str
    dni: str
    correo: str
    roles: tuple
    es_solicitante: bool = False
    tipo: str = ""        # Alumno / Docente / Administrativo (si es solicitante)
    cui: str = ""
    etiqueta: str = ""    # Nuevo / Frecuente / Sancionado / Baneado


@dataclass(frozen=True)
class FichaItem:
    id: UUID
    codigo: str
    nombre: str
    categoria: str
    estado: str           # texto legible: "Disponible", "Prestado", "Dañado"...
    motivo_fuera_servicio: str = ""


class IFuenteDeHistoriales(IFuenteDeReportes):
    """Lo que necesitan los historiales de una persona y de un ítem (solo consulta)."""

    @abstractmethod
    def persona(self, cuenta_id):
        """FichaPersona o None si la cuenta no existe."""

    @abstractmethod
    def buscar_personas(self, q):
        """list[FichaPersona] cuyo nombre, correo, DNI o CUI contiene el texto."""

    @abstractmethod
    def item(self, item_id):
        """FichaItem o None si el ítem no existe."""

    @abstractmethod
    def buscar_items(self, q):
        """list[FichaItem] cuyo código o atributos contienen el texto."""

    @abstractmethod
    def prestamos_de_persona(self, cuenta_id):
        """list[FilaPrestamo], del más reciente al más antiguo."""

    @abstractmethod
    def prestamos_de_item(self, item_id):
        """list[FilaPrestamo], del más reciente al más antiguo."""

    @abstractmethod
    def sanciones_de(self, cuenta_id):
        """Sanciones de la cuenta, de la más reciente a la más antigua."""

    @abstractmethod
    def perdidas_de_persona(self, cuenta_id):
        """Casos de pérdida de la cuenta."""

    @abstractmethod
    def perdidas_de_prestamos(self, prestamo_ids):
        """Casos de pérdida de esos préstamos."""

    @abstractmethod
    def danios_de_item(self, item_id):
        """list[FilaDanio] registrados para el ítem (con quién lo devolvió, si se sabe)."""

    @abstractmethod
    def dni_de_cuentas(self, ids):
        """{cuenta_id: dni}"""
