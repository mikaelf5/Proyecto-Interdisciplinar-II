"""Puertos (interfaces) de persistencia del contexto Identidad."""
from abc import ABC, abstractmethod


class ICuentaRepositorio(ABC):
    @abstractmethod
    def obtener(self, cuenta_id):
        """Cuenta por id, o None si no existe."""

    @abstractmethod
    def por_correo(self, correo):
        """Cuenta por correo (sin distinguir mayúsculas), o None."""

    @abstractmethod
    def guardar(self, cuenta): ...

    @abstractmethod
    def listar(self, q=""): ...


class IPerfilSolicitanteRepositorio(ABC):
    @abstractmethod
    def de_cuenta(self, cuenta_id):
        """Perfil de la cuenta, o None si no tiene."""
