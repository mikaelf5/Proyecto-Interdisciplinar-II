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
    reserva_id: UUID
    encargado_id: UUID
    garantia_tipo: str
    garantia_detalle: str = ""
    terminos_aceptados: bool = False
    descripcion_condicion: str = ""

@dataclass(frozen=True)
class DevolucionDTO:
    prestamo_id: UUID
    encargado_id: UUID
    descripcion_condicion: str
    garantia_devuelta: bool
    item_daniado: bool
    foto: str = ""

@dataclass(frozen=True)
class PrestamoDTO:
    id: UUID
    item_id: UUID
    solicitante_id: UUID
    reserva_id: UUID
    estado: str
    fecha_entrega: datetime
    fecha_vencimiento: datetime

    @classmethod
    def desde_modelo(cls, p):
        return cls(
            id=p.id,
            item_id=p.item_id,
            solicitante_id=p.solicitante_id,
            reserva_id=p.reserva_id,
            estado=p.estado,
            fecha_entrega=p.fecha_entrega,
            fecha_vencimiento=p.fecha_vencimiento,
        )
