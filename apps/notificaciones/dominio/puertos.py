"""
Capa de DOMINIO — puerto IEmisorNotificacion («Port» del PDF).

El dominio dice QUÉ necesita (enviar una notificación); el adaptador
de infraestructura (EmisorCorreoSMTP) decide CÓMO (correo SMTP).
"""
from abc import ABC, abstractmethod


class IEmisorNotificacion(ABC):
    @abstractmethod
    def enviar(self, notificacion):
        """Envía la notificación. Devuelve True si se entregó."""
