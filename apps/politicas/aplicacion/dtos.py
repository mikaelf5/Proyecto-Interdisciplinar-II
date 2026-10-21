from dataclasses import dataclass
from uuid import UUID


@dataclass
class PoliticaDTO:
    tipo_item: str
    tipo_usuario: str
    duracion_maxima: int
    max_renovaciones: int
    antelacion_reserva: int
    limite_simultaneo_global: int
    limite_simultaneo_por_tipo: int
    categoria_id: UUID | None = None