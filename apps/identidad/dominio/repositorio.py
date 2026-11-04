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
    def existe_dni(self, dni) -> bool: ...

    @abstractmethod
    def contar_activas_con_rol(self, rol) -> int: ...

    @abstractmethod
    def guardar(self, cuenta): ...

    @abstractmethod
    def listar(self, q="", rol="", estado=""): ...


class IPerfilSolicitanteRepositorio(ABC):
    @abstractmethod
    def de_cuenta(self, cuenta_id):
        """Perfil de la cuenta, o None si no tiene."""

    @abstractmethod
    def guardar(self, perfil): ...

    @abstractmethod
    def todos(self): ...


class ISolicitudRegistroRepositorio(ABC):
    @abstractmethod
    def obtener(self, solicitud_id):
        """Solicitud por id, o None."""

    @abstractmethod
    def hay_pendiente(self, correo="", dni="") -> bool:
        """¿Ya hay una solicitud PENDIENTE con ese correo o con ese DNI?"""

    @abstractmethod
    def ultima_por_correo(self, correo):
        """La solicitud más reciente con ese correo (cualquier estado), o None."""

    @abstractmethod
    def guardar(self, solicitud): ...

    @abstractmethod
    def listar(self, estado=""): ...

    @abstractmethod
    def contar_pendientes(self) -> int: ...
