from django.db import models

from apps.common.choices import TipoUsuario
from apps.common.models import BaseModel


class PoliticaPrestamo(BaseModel):
    tipo_item = models.CharField(max_length=100)

    tipo_usuario = models.CharField(
        max_length=20,
        choices=TipoUsuario.choices,
    )

    duracion_maxima = models.PositiveIntegerField()
    max_renovaciones = models.PositiveIntegerField()
    antelacion_reserva = models.PositiveIntegerField()
    limite_simultaneo_global = models.PositiveIntegerField()
    limite_simultaneo_por_tipo = models.PositiveIntegerField()

    class Meta:
        verbose_name = "política de préstamo"
        verbose_name_plural = "políticas de préstamo"
        unique_together = ("tipo_item", "tipo_usuario")

    def __str__(self):
        return f"{self.tipo_item} - {self.get_tipo_usuario_display()}"