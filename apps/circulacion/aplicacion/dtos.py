"""Objetos de transferencia del contexto Circulación."""
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

@dataclass(frozen=True)
class SolicitudDTO:
    item_id: UUID | None
    categoria_id: UUID | None
    solicitante_id: UUID
    fecha_inicio: date
    fecha_fin: date
    finalidad: str = ""

@dataclass(frozen=True)
class EntregaPrestamoDTO:
    solicitud_id: UUID
    encargado_id: UUID
    garantia_tipo: str
    garantia_detalle: str = ""
    terminos_aceptados: bool = False
    fecha_vencimiento: datetime | None = None

@dataclass(frozen=True)
class DevolucionDTO:
    prestamo_id: UUID
    encargado_id: UUID
    descripcion_condicion: str
    foto: str = ""

@dataclass(frozen=True)
class PrestamoDTO:
    id: UUID
    item_id: UUID
    solicitante_id: UUID
    estado: str
    fecha_entrega: datetime
    fecha_vencimiento: datetime

    @classmethod
    def desde_modelo(cls, p):
        return cls(p.id, p.item_id, p.solicitante_id, p.estado, p.fecha_entrega, p.fecha_vencimiento)
