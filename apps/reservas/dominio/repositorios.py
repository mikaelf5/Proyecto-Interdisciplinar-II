"""Capa de DOMINIO — interfaz IReservaRepositorio (PDF)."""
from abc import ABC, abstractmethod


class IReservaRepositorio(ABC):
    @abstractmethod
    def guardar(self, reserva): ...

    @abstractmethod
    def buscar_por_id(self, reserva_id): ...

    @abstractmethod
    def cola_de(self, item_id, bloquear=False):
        """Reservas ACTIVAS del ítem, ordenadas por posición."""

    @abstractmethod
    def de_solicitante(self, solicitante_id): ...

    @abstractmethod
    def confirmadas_antes_de(self, fecha_hora): ...
