"""
Capa de APLICACIÓN — INotificacionServicio / NotificacionServicioAplicacion (PDF).

Otros contextos la usan así:
    from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
    NotificacionServicioAplicacion().enviar(solicitante_id, "ALERTA_ATRASO", "Tu préstamo venció")
"""
from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError
from django.db import transaction

from ..dominio.models import Notificacion
from ..infraestructura.emisores import EmisorCorreoSMTP
from ..infraestructura.repositorios import NotificacionRepositorioImpl
from .dtos import NotificacionDTO


class INotificacionServicio(ABC):
    @abstractmethod
    def enviar(self, destinatario_id, tipo, mensaje): ...

    @abstractmethod
    def recordar_vencimientos(self, hoy=None): ...

    @abstractmethod
    def marcar_leida(self, notificacion_id, destinatario_id=None): ...


class NotificacionServicioAplicacion(INotificacionServicio):
    def __init__(self, repositorio=None, emisor=None):
        self.repositorio = repositorio or NotificacionRepositorioImpl()
        self.emisor = emisor or EmisorCorreoSMTP()

    @transaction.atomic
    def enviar(self, destinatario_id, tipo, mensaje):
        notificacion = Notificacion(destinatario_id=destinatario_id, tipo=tipo, mensaje=mensaje)
        if self.emisor.enviar(notificacion):  # puerto → adaptador SMTP
            notificacion.marcar_enviada()
        self.repositorio.guardar(notificacion)  # se guarda siempre (queda el historial)
        return NotificacionDTO.desde(notificacion)

    def reintentar(self, notificacion_id):
        notificacion = self.repositorio.buscar_por_id(notificacion_id)
        if not notificacion.enviada and self.emisor.enviar(notificacion):
            notificacion.marcar_enviada()
            self.repositorio.guardar(notificacion)
        return NotificacionDTO.desde(notificacion)

    def recordar_vencimientos(self, hoy=None):
        """
        Pendiente: necesita IPrestamoServicio.listar_vencidos() de Circulación (Marving).
        Cuando exista: por cada préstamo que vence mañana → enviar(RECORDATORIO_VENCIMIENTO).
        """
        raise NotImplementedError("Depende de IPrestamoServicio.listar_vencidos() (Circulación).")

    @transaction.atomic
    def marcar_leida(self, notificacion_id, destinatario_id=None):
        notificacion = self.repositorio.buscar_por_id(notificacion_id)
        if destinatario_id and notificacion.destinatario_id != destinatario_id:
            raise ValidationError("Esa notificación no es tuya.")
        notificacion.marcar_como_leida()
        self.repositorio.guardar(notificacion)
        return NotificacionDTO.desde(notificacion)

    def mis_notificaciones(self, destinatario_id):
        """NotificacionController.misNotificaciones(request)"""
        return [NotificacionDTO.desde(n) for n in self.repositorio.de_destinatario(destinatario_id)]
