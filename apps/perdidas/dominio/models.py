from django.db import models
from apps.common.models import BaseModel

class CasoPerdida(BaseModel):
    prestamo_id = models.UUIDField(
        help_text="Préstamo asociado a la pérdida/daño (contexto Circulación)."
    )
    solicitante_id = models.UUIDField(
        help_text="Solicitante responsable del ítem perdido/dañado (contexto Identidad)."
    )
    fecha = models.DateField()
    observaciones = models.TextField(blank=True)
    costo_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Costo de reposición estimado del ítem.",
    )
    cerrado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Caso de pérdida"
        verbose_name_plural = "Casos de pérdida"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pérdida {self.id} · préstamo {self.prestamo_id}"

    def cerrar_prestamo(self):
        """
        Stub (fase de lógica de negocio). Cuando se implemente deberá:
        - Marcar el Prestamo (prestamo_id) como CERRADO_POR_PERDIDA.
        - Disparar una Sancion sobre el solicitante si corresponde.
        - Dejar constancia en RegistroAuditoria.
        Por ahora solo marca el caso como cerrado localmente.
        """
        self.cerrado = True
        self.save(update_fields=["cerrado"])
