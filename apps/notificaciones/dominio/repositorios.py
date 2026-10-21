"""Capa de DOMINIO — interfaz INotificacionRepositorio (PDF)."""
from abc import ABC, abstractmethod


class INotificacionRepositorio(ABC):
    @abstractmethod
    def guardar(self, notificacion): ...

    @abstractmethod
    def buscar_por_id(self, notificacion_id): ...

    @abstractmethod
    def de_destinatario(self, destinatario_id): ...
