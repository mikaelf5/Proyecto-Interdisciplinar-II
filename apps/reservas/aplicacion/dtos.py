from dataclasses import dataclass
from datetime import date, time
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class NuevaReservaDTO:
    """Lo que llega desde la pantalla para crear una reserva."""
    solicitante_id: UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    item_id: Optional[UUID] = None       # ítem concreto…
    categoria_id: Optional[UUID] = None  # …o cualquier ítem libre de la categoría
    finalidad: str = ""


@dataclass(frozen=True)
class ReservaDTO:
    id: UUID
    item_id: UUID
    categoria_id: Optional[UUID]
    solicitante_id: UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    finalidad: str
    estado: str
    estado_display: str
    posicion_en_cola: Optional[int]
    motivo: str
    aprobado_por_supervisor_id: Optional[UUID]

    @property
    def franja(self):
        return f"{self.fecha:%d/%m/%Y} de {self.hora_inicio:%H:%M} a {self.hora_fin:%H:%M}"

    @property
    def se_puede_cancelar(self):
        return self.estado in ("ACTIVA", "EN_ESPERA_SUPERVISOR", "CONFIRMADA")

    @property
    def se_puede_anular(self):
        return self.estado in ("EN_ESPERA_SUPERVISOR", "CONFIRMADA")

    @classmethod
    def desde(cls, r):
        return cls(
            id=r.id, item_id=r.item_id, categoria_id=r.categoria_id, solicitante_id=r.solicitante_id,
            fecha=r.fecha, hora_inicio=r.hora_inicio, hora_fin=r.hora_fin, finalidad=r.finalidad,
            estado=r.estado, estado_display=r.get_estado_display(),
            posicion_en_cola=r.posicion_en_cola, motivo=r.motivo,
            aprobado_por_supervisor_id=r.aprobado_por_supervisor_id,
        )
