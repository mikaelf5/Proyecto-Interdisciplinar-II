from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.common.choices import EstadoSolicitud, EstadoPrestamo, TipoGarantia
from apps.common.models import BaseModel


class Solicitud(BaseModel):
    item_id = models.UUIDField(null=True, blank=True, db_index=True)
    categoria_id = models.UUIDField(null=True, blank=True, db_index=True)

    solicitante_id = models.UUIDField(db_index=True)
    revisado_por_id = models.UUIDField(null=True, blank=True, db_index=True)
    aprobado_por_supervisor_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    finalidad = models.TextField(blank=True)

    estado = models.CharField(
        max_length=30,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE,
    )

    motivo_rechazo = models.TextField(blank=True)

    class Meta:
        verbose_name = "solicitud"
        verbose_name_plural = "solicitudes"

    def __str__(self):
        return f"Solicitud {self.id} - {self.estado}"

    def clean(self):
        super().clean()

        if not self.item_id and not self.categoria_id:
            raise ValidationError(
                "La solicitud debe indicar un ítem o una categoría."
            )

        if self.item_id and self.categoria_id:
            raise ValidationError(
                "La solicitud no puede indicar un ítem y una categoría al mismo tiempo."
            )

        if self.fecha_fin < self.fecha_inicio:
            raise ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )

    def aprobar(self):
        self.estado = EstadoSolicitud.APROBADA

    def aprobar_como_supervisor(self, supervisor_id):
        self.aprobado_por_supervisor_id = supervisor_id
        self.estado = EstadoSolicitud.APROBADA

    def rechazar(self, motivo):
        self.motivo_rechazo = motivo
        self.estado = EstadoSolicitud.RECHAZADA

    def cancelar(self):
        self.estado = EstadoSolicitud.CANCELADA

    def requiere_supervisor(self):
        return self.estado == EstadoSolicitud.EN_ESPERA_SUPERVISOR

class Prestamo(BaseModel):
    item_id = models.UUIDField(db_index=True)
    solicitante_id = models.UUIDField(db_index=True)
    solicitud_id = models.UUIDField(db_index=True)

    encargado_entrega_id = models.UUIDField(db_index=True)
    encargado_devolucion_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    garantia_tipo = models.CharField(
        max_length=30,
        choices=TipoGarantia.choices,
    )
    garantia_detalle = models.TextField(blank=True)
    garantia_devuelta = models.BooleanField(default=False)

    terminos_aceptados = models.BooleanField(default=False)

    fecha_entrega = models.DateTimeField()
    fecha_vencimiento = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(
        null=True,
        blank=True,
    )

    estado = models.CharField(
        max_length=30,
        choices=EstadoPrestamo.choices,
        default=EstadoPrestamo.ACTIVO,
    )

    renovaciones_realizadas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "préstamo"
        verbose_name_plural = "préstamos"

    def __str__(self):
        return f"Préstamo {self.id} - {self.estado}"

    def esta_vencido(self):
        return (
            self.estado == EstadoPrestamo.ACTIVO
            and timezone.now() > self.fecha_vencimiento
        )