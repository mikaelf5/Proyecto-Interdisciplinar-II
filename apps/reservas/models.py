"""
Contexto: Reservas (Partnership).

Agregado Reserva: un solicitante hace cola (FIFO) para un ítem que no está
disponible. Las referencias a Item (Catálogo) y al solicitante (Identidad)
son por UUID, sin ForeignKey, para respetar la frontera del contexto.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Q

from apps.common.choices import EstadoReserva
from apps.common.models import BaseModel


class Reserva(BaseModel):
    item_id = models.UUIDField("ítem", db_index=True)
    solicitante_id = models.UUIDField("solicitante", db_index=True)
    posicion_en_cola = models.PositiveIntegerField(
        "posición en cola",
        blank=True,
        help_text="Déjalo vacío para ponerlo al final de la cola.",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoReserva.choices,
        default=EstadoReserva.ACTIVA,
    )

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["item_id", "posicion_en_cola"]
        constraints = [
            # Invariante FIFO: dentro de la cola activa de un ítem
            # no puede haber dos reservas en la misma posición.
            models.UniqueConstraint(
                fields=["item_id", "posicion_en_cola"],
                condition=Q(estado="ACTIVA"),
                name="reserva_posicion_unica_por_item_activa",
            ),
            # Un solicitante no puede tener dos reservas activas del mismo ítem.
            models.UniqueConstraint(
                fields=["item_id", "solicitante_id"],
                condition=Q(estado="ACTIVA"),
                name="reserva_unica_activa_por_solicitante_item",
            ),
        ]

    def __str__(self):
        return f"Reserva #{self.posicion_en_cola} · ítem {self.item_id} · {self.get_estado_display()}"

    # ---------- Cola FIFO ----------
    @classmethod
    def siguiente_posicion(cls, item_id):
        """Devuelve la posición que le toca a una nueva reserva del ítem."""
        ultima = cls.objects.filter(
            item_id=item_id, estado=EstadoReserva.ACTIVA
        ).aggregate(m=Max("posicion_en_cola"))["m"]
        return (ultima or 0) + 1

    def save(self, *args, **kwargs):
        # Si no se indicó posición, se coloca al final de la cola.
        if self.posicion_en_cola is None:
            self.posicion_en_cola = Reserva.siguiente_posicion(self.item_id)
        super().save(*args, **kwargs)

    # ---------- Transiciones de estado ----------
    def _cambiar_estado(self, nuevo, permitidos):
        if self.estado not in permitidos:
            raise ValidationError(
                f"No se puede pasar de {self.get_estado_display()} a "
                f"{EstadoReserva(nuevo).label}."
            )
        self.estado = nuevo
        self.save(update_fields=["estado"])

    def confirmar(self):
        """El ítem quedó disponible para este solicitante (ACTIVA → CONFIRMADA)."""
        self._cambiar_estado(EstadoReserva.CONFIRMADA, {EstadoReserva.ACTIVA})

    def expirar(self):
        """El solicitante no recogió el ítem a tiempo."""
        self._cambiar_estado(
            EstadoReserva.EXPIRADA,
            {EstadoReserva.ACTIVA, EstadoReserva.CONFIRMADA},
        )

    def cancelar(self):
        """El solicitante desiste de la reserva."""
        self._cambiar_estado(
            EstadoReserva.CANCELADA,
            {EstadoReserva.ACTIVA, EstadoReserva.CONFIRMADA},
        )
