"""Capa de INFRAESTRUCTURA — NotificacionRepositorioImpl (Django ORM + PostgreSQL)."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from ..dominio.models import Notificacion
from ..dominio.repositorios import INotificacionRepositorio


class NotificacionRepositorioImpl(INotificacionRepositorio):
    def guardar(self, notificacion):
        notificacion.full_clean()
        notificacion.save()

    def buscar_por_id(self, notificacion_id):
        try:
            return Notificacion.objects.get(pk=notificacion_id)
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise ValidationError("La notificación no existe.")

    def de_destinatario(self, destinatario_id):
        return list(Notificacion.objects.filter(destinatario_id=destinatario_id).order_by("-creado_en"))
