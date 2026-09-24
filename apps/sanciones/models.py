from django.db import models
from apps.common.models import BaseModel

class TipoSancion(models.TextChoices):
    OBSERVACION = "OBSERVACION", "Observación"
    SUSPENSION_TEMPORAL = "SUSPENSION_TEMPORAL", "Suspensión temporal"
    BANEO = "BANEO", "Baneo"


class Sancion(BaseModel):
    # Referencias por UUID (cruzan de contexto -> sin ForeignKey)
    solicitante_id = models.UUIDField(
        help_text="Referencia al PerfilSolicitante/Cuenta sancionado (contexto Identidad)."
    )
    aplicada_por_id = models.UUIDField(
        help_text="Referencia al Personal/Encargado que aplicó la sanción (contexto Identidad)."
    )
    prestamo_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Préstamo que originó la sanción, si aplica (contexto Circulación).",
    )

    tipo = models.CharField(max_length=30, choices=TipoSancion.choices)
    motivo = models.TextField()
    duracion_dias = models.PositiveIntegerField(
        null=True, blank=True, help_text="Días de suspensión, si el tipo lo requiere."
    )
    fecha_inicio = models.DateField()
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sanción"
        verbose_name_plural = "Sanciones"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        estado = "activa" if self.activa else "cerrada"
        return f"{self.get_tipo_display()} · {self.solicitante_id} ({estado})"

    def cerrar(self):
        """Marca la sanción como cumplida/condonada."""
        self.activa = False
        self.save(update_fields=["activa"])
