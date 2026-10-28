"""
Capa de DOMINIO — interfaces de repositorio (los «Repository» del PDF).

El dominio solo define QUÉ se puede guardar/buscar. CÓMO se hace
(Django ORM + PostgreSQL) está en infraestructura/repositorios.py.
"""
from abc import ABC, abstractmethod


class ICategoriaRepositorio(ABC):
    @abstractmethod
    def guardar(self, categoria): ...

    @abstractmethod
    def buscar_por_id(self, categoria_id): ...

    @abstractmethod
    def todas(self): ...


class IItemRepositorio(ABC):
    @abstractmethod
    def guardar(self, item): ...

    @abstractmethod
    def buscar_por_id(self, item_id): ...

    @abstractmethod
    def buscar_por_codigo(self, codigo): ...

    @abstractmethod
    def buscar(self, filtros): ...


class ICondicionFisicaRepositorio(ABC):
    @abstractmethod
    def guardar(self, condicion): ...

    @abstractmethod
    def de_item(self, item_id): ...
