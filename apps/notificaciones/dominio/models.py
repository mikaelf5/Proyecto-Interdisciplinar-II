"""
Capa de DOMINIO — Contexto: Notificaciones (Generic).

Agregado Notificacion: mensaje dirigido a un solicitante o miembro del personal.
El destinatario se referencia por UUID (vive en Identidad). Canal: CORREO.
Los métodos cambian el estado pero NO guardan (eso lo hace el repositorio).
"""
from django.db import models
from django.utils import timezone

from apps.common.choices import CanalNotificacion, TipoNotificacion
from apps.common.models import BaseModel


class Notificacion(BaseModel):
    destinatario_id = models.UUIDField("destinatario", db_index=True)
    tipo = models.CharField(max_length=40, choices=TipoNotificacion.choices)
    canal = models.CharField(
        max_length=20,
        choices=CanalNotificacion.choices,
        default=CanalNotificacion.CORREO,
    )
    mensaje = models.TextField()
    fecha_envio = models.DateTimeField("fecha de envío", null=True, blank=True)
    leida = models.BooleanField("leída", default=False)

    class Meta:
        app_label = "notificaciones"
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.destinatario_id}"

    @property
    def enviada(self):
        return self.fecha_envio is not None

    def marcar_enviada(self):
        """Registra el momento en que el emisor la entregó."""
        self.fecha_envio = timezone.now()

    def marcar_como_leida(self):
        self.leida = True
