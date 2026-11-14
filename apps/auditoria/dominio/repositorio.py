from abc import ABC, abstractmethod


class IRegistroAuditoriaRepositorio(ABC):
    @abstractmethod
    def guardar(self, registro): ...

    @abstractmethod
    def buscar(self, filtros): ...

    @abstractmethod
    def entidades(self):
        """Nombres de entidad que ya aparecen en la bitácora (para el filtro)."""

    @abstractmethod
    def nombres_de_actores(self, ids):
        """{cuenta_id: nombres} de quienes hicieron las acciones."""
