from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class NotificacionDTO:
    id: UUID
    destinatario_id: UUID
    tipo: str
    tipo_display: str
    mensaje: str
    fecha_envio: Optional[datetime]
    leida: bool
    creado_en: datetime

    @classmethod
    def desde(cls, n):
        return cls(id=n.id, destinatario_id=n.destinatario_id, tipo=n.tipo,
                   tipo_display=n.get_tipo_display(), mensaje=n.mensaje,
                   fecha_envio=n.fecha_envio, leida=n.leida, creado_en=n.creado_en)
