from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.common.choices import EstadoSolicitud, EstadoPrestamo, TipoGarantia
from apps.common.models import BaseModel
from django.db.models import Q


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
        app_label = "circulacion"
        verbose_name = "solicitud"
        verbose_name_plural = "solicitudes"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Solicitud {self.id} - {self.estado}"

    TRANSICIONES_PERMITIDAS = {
        EstadoSolicitud.PENDIENTE: [
            EstadoSolicitud.APROBADA,
            EstadoSolicitud.EN_ESPERA_SUPERVISOR,
            EstadoSolicitud.RECHAZADA,
            EstadoSolicitud.CANCELADA,
        ],
        EstadoSolicitud.EN_ESPERA_SUPERVISOR: [
            EstadoSolicitud.APROBADA,
            EstadoSolicitud.RECHAZADA,
        ],
        EstadoSolicitud.APROBADA: [],
        EstadoSolicitud.RECHAZADA: [],
        EstadoSolicitud.CANCELADA: [],
    }

    def validar_transicion(self, nuevo_estado):
        permitidos = self.TRANSICIONES_PERMITIDAS.get(self.estado, [])

        if nuevo_estado not in permitidos:
            raise ValidationError(
                f"No se puede cambiar una solicitud de {self.estado} a {nuevo_estado}."
            )

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

        if self.fecha_inicio is not None and self.fecha_fin is not None:
            if self.fecha_fin < self.fecha_inicio:
                raise ValidationError(
                    "La fecha de fin no puede ser anterior a la fecha de inicio."
                )

    def aprobar(self, revisor_id):
        if self.estado != EstadoSolicitud.PENDIENTE:
            raise ValidationError(
                "Solo se pueden aprobar directamente las solicitudes pendientes."
            )

        self.validar_transicion(EstadoSolicitud.APROBADA)

        if revisor_id is None:
            raise ValidationError(
                "Debe indicarse quién aprueba la solicitud."
            )

        self.revisado_por_id = revisor_id
        self.estado = EstadoSolicitud.APROBADA
        self.save()

    def aprobar_como_supervisor(self, supervisor_id):
        if self.estado != EstadoSolicitud.EN_ESPERA_SUPERVISOR:
            raise ValidationError(
                "Solo se pueden aprobar como supervisor las solicitudes en espera de supervisor."
            )

        self.validar_transicion(EstadoSolicitud.APROBADA)

        if supervisor_id is None:
            raise ValidationError(
                "Debe indicar quién aprueba la solicitud."
            )

        self.aprobado_por_supervisor_id = supervisor_id
        self.estado = EstadoSolicitud.APROBADA
        self.save()

    def rechazar(self, motivo, revisor_id):
        self.validar_transicion(EstadoSolicitud.RECHAZADA)

        if not motivo or not motivo.strip():
            raise ValidationError(
                "Debe indicar un motivo para rechazar la solicitud."
            )

        if revisor_id is None:
            raise ValidationError(
                "Debe indicar quién rechaza la solicitud."
            )

        self.motivo_rechazo = motivo.strip()
        self.revisado_por_id = revisor_id
        self.estado = EstadoSolicitud.RECHAZADA
        self.save()

    def cancelar(self):
        self.validar_transicion(EstadoSolicitud.CANCELADA)

        self.estado = EstadoSolicitud.CANCELADA
        self.save()

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
        app_label = "circulacion"
        verbose_name = "préstamo"
        verbose_name_plural = "préstamos"
        ordering = ["-fecha_entrega"]

        constraints = [
            models.UniqueConstraint(
                fields=["item_id"],
                condition=Q(
                    estado__in=[
                        EstadoPrestamo.ACTIVO,
                        EstadoPrestamo.VENCIDO,
                    ]
                ),
                name="unique_prestamo_abierto_por_item",
            )
        ]

    def clean(self):
        super().clean()

        if self.fecha_entrega is not None and self.fecha_vencimiento is not None:
            if self.fecha_vencimiento <= self.fecha_entrega:
                raise ValidationError(
                    "La fecha de vencimiento debe ser posterior a la fecha de entrega."
                )

    def __str__(self):
        return f"Préstamo {self.id} - {self.estado}"

    def esta_vencido(self):
        return (
            self.estado == EstadoPrestamo.ACTIVO
            and timezone.now() > self.fecha_vencimiento
        )

    def renovar(self, politica):
        """Extiende un préstamo vigente por la duración autorizada en horas."""
        if self.estado != EstadoPrestamo.ACTIVO or self.esta_vencido():
            raise ValidationError("Solo se puede renovar un préstamo activo y no vencido.")
        if not politica.permite_renovar(self.renovaciones_realizadas):
            raise ValidationError("Se alcanzó el límite de renovaciones.")
        if politica.duracion_maxima <= 0:
            raise ValidationError("La duración de la política debe ser positiva.")
        from datetime import timedelta
        self.fecha_vencimiento += timedelta(hours=politica.duracion_maxima)
        self.renovaciones_realizadas += 1
        self.full_clean()
        self.save(update_fields=["fecha_vencimiento", "renovaciones_realizadas", "actualizado_en"])

    def registrar_devolucion(self, estado_fisico=None, encargado_id=None, fecha=None):
        """Cierra el préstamo; el registro físico se delega a Catálogo."""
        if self.estado not in (EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO):
            raise ValidationError("El préstamo no está abierto.")
        if encargado_id is None:
            raise ValidationError("Se requiere el encargado de la devolución.")
        fecha = fecha or timezone.now()
        if fecha < self.fecha_entrega:
            raise ValidationError("La devolución no puede preceder a la entrega.")
        self.fecha_devolucion_real = fecha
        self.encargado_devolucion_id = encargado_id
        self.estado = EstadoPrestamo.DEVUELTO
        self.save(update_fields=["fecha_devolucion_real", "encargado_devolucion_id", "estado", "actualizado_en"])

    def cerrar_por_perdida(self):
        if self.estado not in (EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO):
            raise ValidationError("Solo se puede cerrar por pérdida un préstamo abierto.")
        self.estado = EstadoPrestamo.CERRADO_POR_PERDIDA
        self.save(update_fields=["estado", "actualizado_en"])
