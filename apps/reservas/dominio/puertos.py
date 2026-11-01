"""
Capa de DOMINIO — puertos hacia otros contextos.

Reservas necesita preguntar cosas a Identidad (¿está habilitado?, ¿qué tipo
de usuario es?) y a Políticas (¿cuánto puede durar?, ¿con cuánta antelación?).
Aquí solo se define QUÉ se pregunta; las respuestas las dan los adaptadores
de infraestructura/adaptadores.py, que llaman a los servicios de esos módulos.
"""
from abc import ABC, abstractmethod


class IIdentidadPuerto(ABC):
    @abstractmethod
    def habilitacion(self, cuenta_id):
        """Devuelve (habilitado: bool, mensaje: str)."""

    @abstractmethod
    def tipo_usuario(self, cuenta_id):
        """ALUMNO / DOCENTE / ADMINISTRATIVO, o None si no tiene perfil."""


class IPoliticasPuerto(ABC):
    @abstractmethod
    def politica_para(self, categoria_id, tipo_usuario):
        """Objeto con duracion_maxima (horas), antelacion_reserva (días),
        limite_simultaneo_global y limite_simultaneo_por_tipo; o None."""
