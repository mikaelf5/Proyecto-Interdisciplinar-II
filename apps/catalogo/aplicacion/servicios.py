"""
Capa de APLICACIÓN — ICatalogoServicio / CatalogoServicioAplicacion (PDF).

Orquesta los casos de uso del Catálogo:
    1. busca el agregado en el repositorio,
    2. aplica la regla del dominio,
    3. lo guarda con el repositorio,
    4. devuelve un DTO.

Las vistas (presentación) y los OTROS contextos (p. ej. Circulación)
solo deben usar esta clase, nunca los modelos directamente:

    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    catalogo = CatalogoServicioAplicacion()
    catalogo.cambiar_estado_item(item_id, "PRESTADO")
"""
from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError
from django.db import transaction
from apps.common.choices import EstadoItem

from ..dominio.models import Categoria, CondicionFisica, Item
from ..infraestructura.repositorios import (
    CategoriaRepositorioImpl,
    CondicionFisicaRepositorioImpl,
    ItemRepositorioImpl,
)
from .dtos import CategoriaDTO, CondicionDTO, FiltrosItem, ItemDTO


class ICatalogoServicio(ABC):
    
    @abstractmethod
    def crear_categoria(self, nombre, es_especial=False, definicion_atributos=None): ...

    @abstractmethod
    def listar_categorias(self): ...

    @abstractmethod
    def registrar_item(self, dto): ...

    @abstractmethod
    def cambiar_estado_item(self, item_id, estado, motivo=""): ...

    @abstractmethod
    def marcar_daniado(self, item_id, motivo): ...

    @abstractmethod
    def dar_de_baja_item(self, item_id, motivo): ...

    @abstractmethod
    def registrar_condicion(self, dto): ...

    @abstractmethod
    def marcar_prestado(self, item_id): ...

    @abstractmethod
    def marcar_disponible(self, item_id): ...
    @abstractmethod
    def buscar_items(self, filtros=None): ...

    # Consultas que usan otros módulos (Circulación, Reservas)
    @abstractmethod
    def obtener_item(self, item_id): ...

    @abstractmethod
    def es_especial(self, item_id=None, categoria_id=None): ...

    @abstractmethod
    def esta_disponible(self, item_id): ...

    @abstractmethod
    def historial_condicion(self, item_id): ...


class CatalogoServicioAplicacion(ICatalogoServicio):
    def __init__(self, items=None, categorias=None, condiciones=None, reservas=None):
        """Inyección de dependencias: en las pruebas se pueden pasar versiones falsas."""
        self.items = items or ItemRepositorioImpl()
        self.categorias = categorias or CategoriaRepositorioImpl()
        self.condiciones = condiciones or CondicionFisicaRepositorioImpl()
        self._reservas = reservas

    # Categorías
    @transaction.atomic
    def crear_categoria(self, nombre, es_especial=False, definicion_atributos=None):
        categoria = Categoria(
            nombre=nombre, es_especial=es_especial,
            definicion_atributos=definicion_atributos or {},
        )
        self.categorias.guardar(categoria)
        return CategoriaDTO.desde(categoria)

    def listar_categorias(self):
        """Desplegable de categorías (buscador y "Registrar ítem")."""
        return [CategoriaDTO.desde(c) for c in self.categorias.todas()]

    # Ítems
    @transaction.atomic
    def registrar_item(self, dto):
        """Botón "Registrar" de la pantalla Registrar ítem (RF-A2, RF-A3: código único)."""
        if self.items.buscar_por_codigo(dto.codigo):
            raise ValidationError(f"Ya existe un ítem con el código {dto.codigo}.")
        categoria = self.categorias.buscar_por_id(dto.categoria_id)
        item = Item(codigo=dto.codigo, categoria=categoria, atributos=dto.atributos)
        self.items.guardar(item)  # aquí se validan los atributos dinámicos
        return ItemDTO.desde(item)

    @transaction.atomic
    def cambiar_estado_item(self, item_id, estado, motivo=""):
        """Botón "Poner disponible" (y Préstamos al entregar/devolver)."""
        item = self.items.buscar_por_id(item_id)
        item.cambiar_estado(estado, motivo)  # regla de dominio (máquina de estados)
        self.items.guardar_estado(item)
        return ItemDTO.desde(item)

    @transaction.atomic
    def marcar_daniado(self, item_id, motivo):
        """Botón "Marcar dañado": pasa a MANTENIMIENTO y anula sus reservas futuras."""
        item = self.items.buscar_por_id(item_id)
        item.marcar_daniado(motivo)
        self.items.guardar_estado(item)
        self._anular_reservas_futuras(item)
        return ItemDTO.desde(item)

    @transaction.atomic
    def dar_de_baja_item(self, item_id, motivo):
        """Botón "Dar de baja": retiro definitivo y anula sus reservas futuras."""
        item = self.items.buscar_por_id(item_id)
        item.dar_de_baja(motivo)
        self.items.guardar_estado(item)
        self._anular_reservas_futuras(item)
        return ItemDTO.desde(item)

    def _anular_reservas_futuras(self, item):
        """Nadie debe llegar a recoger un ítem que ya no está en servicio (RF-A4)."""
        motivo = f"{item.codigo} quedó fuera de servicio: {item.motivo_fuera_servicio}"
        self._servicio_de_reservas().anular_reservas_del_item(item.id, motivo)

    def _servicio_de_reservas(self):
        if self._reservas is None:
            from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion  # evita importación circular
            self._reservas = ReservaServicioAplicacion(catalogo=self)
        return self._reservas
    
    def marcar_prestado(self, item_id):
        """Lo llama Circulación al entregar un préstamo."""
        return self.cambiar_estado_item(item_id, EstadoItem.PRESTADO)

    def marcar_disponible(self, item_id):
        """Lo llama Circulación al registrar una devolución sin daños."""
        return self.cambiar_estado_item(item_id, EstadoItem.DISPONIBLE)
    
    @transaction.atomic
    def registrar_condicion(self, dto):
        item = self.items.buscar_por_id(dto.item_id)
        condicion = CondicionFisica(
            item=item, prestamo_id=dto.prestamo_id, responsable_id=dto.responsable_id,
            momento=dto.momento, fecha=dto.fecha, descripcion=dto.descripcion, foto=dto.foto,
        )
        self.condiciones.guardar(condicion)
        return condicion.id

    def buscar_items(self, filtros=None):
        """Botón "Buscar" del catálogo."""
        return [ItemDTO.desde(i) for i in self.items.buscar(filtros or FiltrosItem())]

    # Consultas para otros módulos
    def obtener_item(self, item_id):
        return ItemDTO.desde(self.items.buscar_por_id(item_id))

    def es_especial(self, item_id=None, categoria_id=None):
        """Lo usa Circulación (ServicioDeAprobacion) para saber si va a supervisor."""
        if item_id:
            return self.items.buscar_por_id(item_id).categoria.es_especial
        if categoria_id:
            return self.categorias.buscar_por_id(categoria_id).es_especial
        raise ValidationError("Indica un ítem o una categoría.")

    def esta_disponible(self, item_id):
        return self.items.buscar_por_id(item_id).esta_disponible

    def historial_condicion(self, item_id):
        """Historial de condición física del ítem, del más reciente al más antiguo (RF-A5)."""
        return [CondicionDTO.desde(c) for c in self.condiciones.de_item(item_id)]
