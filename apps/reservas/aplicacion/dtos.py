from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReservaDTO:
    id: UUID
    item_id: UUID
    solicitante_id: UUID
    posicion_en_cola: int
    estado: str
    estado_display: str

    @classmethod
    def desde(cls, r):
        return cls(id=r.id, item_id=r.item_id, solicitante_id=r.solicitante_id,
                   posicion_en_cola=r.posicion_en_cola, estado=r.estado,
                   estado_display=r.get_estado_display())
