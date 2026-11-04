"""Puertos de persistencia de Circulación según el modelo extendido."""
from abc import ABC, abstractmethod


class IPrestamoRepositorio(ABC):
    @abstractmethod
    def guardar(self, prestamo): ...
    @abstractmethod
    def buscar_por_id(self, prestamo_id): ...
    @abstractmethod
    def vigentes_de(self, solicitante_id): ...

    @abstractmethod
    def historial_de(self, solicitante_id): ...
    @abstractmethod
    def vencidos(self): ...
    @abstractmethod
    def buscar_vencidos(self, solicitante_id=None, item_id=None): ...
    @abstractmethod
    def existe_abierto_para_item(self, item_id): ...
    def obtener_por_id(self, prestamo_id):
        return self.buscar_por_id(prestamo_id)

    @abstractmethod
    def entregados_hoy(self):
        ...

    @abstractmethod
    def abiertos(self):
        """Retorna todos los préstamos activos y vencidos."""
        ...
