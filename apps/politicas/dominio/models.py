from django.db import models

from apps.common.choices import TipoUsuario
from apps.common.models import BaseModel
from datetime import timedelta
from django.core.exceptions import ValidationError


class PoliticaPrestamo(BaseModel):
    tipo_item = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    categoria_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True
    )

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
        app_label = "politicas"
        verbose_name = "política de préstamo"
        verbose_name_plural = "políticas de préstamo"
        unique_together = ("tipo_item", "tipo_usuario")
        constraints = [
            models.UniqueConstraint(
                fields=["categoria_id", "tipo_usuario"],
                name="politica_unica_por_categoria_usuario"
            )
        ]

    def __str__(self):
        identificador = self.categoria_id or self.tipo_item
        return f"{identificador} - {self.get_tipo_usuario_display()}"

    def calcular_vencimiento(self, desde):
        return desde + timedelta(hours=self.duracion_maxima)

    def validar_plazo(self, fecha_entrega, fecha_devolucion):
        if fecha_devolucion <= fecha_entrega:
            return False

        fecha_limite = self.calcular_vencimiento(fecha_entrega)

        return fecha_devolucion <= fecha_limite

    def permite_renovar(self, realizadas):
        return realizadas < self.max_renovaciones

    def clean(self):
        super().clean()
        if not self.tipo_item and not self.categoria_id:
            raise ValidationError(
                "Debe indicar un tipo de ítem o una categoría."
            )

        if self.duracion_maxima <= 0:
            raise ValidationError(
                "La duración máxima debe ser mayor que cero."
            )

        if self.limite_simultaneo_global <= 0:
            raise ValidationError(
                "El límite global debe ser mayor que cero."
            )

        if self.limite_simultaneo_por_tipo <= 0:
            raise ValidationError(
                "El límite por tipo debe ser mayor que cero."
            )

        if self.limite_simultaneo_por_tipo > self.limite_simultaneo_global:
            raise ValidationError(
                "El límite por tipo no puede superar el límite global."
            )