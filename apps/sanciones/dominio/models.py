from datetime import date, timedelta
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

    def fecha_fin(self):
        """Último día de la sanción, o None si no tiene plazo (ej. baneo)."""
        if self.duracion_dias:
            return self.fecha_inicio + timedelta(days=self.duracion_dias - 1)
        return None

    def esta_vigente(self, hoy=None):
        hoy = hoy or date.today()
        if not self.activa:
            return False
        fin = self.fecha_fin()
        return fin is None or hoy <= fin

    def levantar(self):
        """Marca la sanción como levantada a mano."""
        self.activa = False
        self.save(update_fields=["activa"])