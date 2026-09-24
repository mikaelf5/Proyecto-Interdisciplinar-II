"""
Contexto: Notificaciones (Generic).

Agregado Notificacion: mensaje dirigido a un solicitante o miembro del personal.
El destinatario se referencia por UUID (vive en Identidad). Por ahora el único
canal es CORREO; el envío real se implementa en la siguiente fase.
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
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.destinatario_id}"

    @property
    def enviada(self):
        return self.fecha_envio is not None

    def marcar_enviada(self):
        """Registra el momento del envío (el envío real llega en la siguiente fase)."""
        self.fecha_envio = timezone.now()
        self.save(update_fields=["fecha_envio"])

    def marcar_como_leida(self):
        self.leida = True
        self.save(update_fields=["leida"])
