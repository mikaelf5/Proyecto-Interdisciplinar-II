"""
Capa de APLICACIÓN — DTOs: lo que el servicio devuelve a la presentación
(o a otros contextos). Así nadie de afuera manipula los modelos directamente.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class CategoriaDTO:
    id: UUID
    nombre: str
    es_especial: bool
    definicion_atributos: dict

    @classmethod
    def desde(cls, c):
        return cls(id=c.id, nombre=c.nombre, es_especial=c.es_especial,
                   definicion_atributos=c.definicion_atributos)


@dataclass(frozen=True)
class ItemDTO:
    id: UUID
    codigo: str
    categoria_id: UUID
    categoria_nombre: str
    categoria_es_especial: bool
    estado: str
    estado_display: str
    atributos: dict
    motivo_fuera_servicio: str

    @property
    def esta_disponible(self):
        return self.estado == "DISPONIBLE"

    @property
    def nombre(self):
        """Nombre legible: usa titulo/nombre/prenda según la categoría."""
        a = self.atributos or {}
        return a.get("titulo") or a.get("nombre") or a.get("prenda") or self.codigo

    @classmethod
    def desde(cls, i):
        return cls(
            id=i.id, codigo=i.codigo,
            categoria_id=i.categoria_id, categoria_nombre=i.categoria.nombre,
            categoria_es_especial=i.categoria.es_especial,
            estado=i.estado, estado_display=i.get_estado_display(),
            atributos=i.atributos, motivo_fuera_servicio=i.motivo_fuera_servicio,
        )


@dataclass(frozen=True)
class FiltrosItem:
    texto: str = ""
    categoria_id: Optional[UUID] = None
    estado: str = ""


@dataclass(frozen=True)
class NuevoItemDTO:
    codigo: str
    categoria_id: UUID
    atributos: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NuevaCondicionDTO:
    item_id: UUID
    prestamo_id: UUID
    responsable_id: UUID
    momento: str          # MomentoRegistro: ENTREGA / DEVOLUCION
    fecha: date
    descripcion: str
    foto: str = ""
