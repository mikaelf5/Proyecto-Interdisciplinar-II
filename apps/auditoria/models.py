from django.db import models
from apps.common.models import BaseModel

class TipoAccion(models.TextChoices):
    ENTREGA = "ENTREGA", "Entrega"
    DEVOLUCION = "DEVOLUCION", "Devolución"
    CAMBIO_ESTADO = "CAMBIO_ESTADO", "Cambio de estado"
    APROBACION = "APROBACION", "Aprobación"
    RECHAZO = "RECHAZO", "Rechazo"
    SANCION = "SANCION", "Sanción"
    ITEM_DANIADO = "ITEM_DANIADO", "Ítem dañado"


class RegistroAuditoria(BaseModel):
    actor_id = models.UUIDField(
        help_text="Personal que realizó la acción (contexto Identidad)."
    )
    accion = models.CharField(max_length=30, choices=TipoAccion.choices)
    entidad = models.CharField(
        max_length=100,
        help_text="Nombre de la entidad afectada, ej. 'Prestamo', 'Item', 'Solicitud'.",
    )
    entidad_id = models.UUIDField(help_text="ID de la entidad afectada.")
    motivo = models.TextField(blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"[{self.fecha_hora:%Y-%m-%d %H:%M}] {self.get_accion_display()} · {self.entidad}({self.entidad_id})"

    @classmethod
    def registrar(cls, *, actor_id, accion, entidad, entidad_id, motivo=""):
        """
        Helper para dejar constancia desde cualquier servicio del dominio:

            RegistroAuditoria.registrar(
                actor_id=encargado.id,
                accion=TipoAccion.ENTREGA,
                entidad="Prestamo",
                entidad_id=prestamo.id,
            )
        """
        return cls.objects.create(
            actor_id=actor_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            motivo=motivo,
        )
