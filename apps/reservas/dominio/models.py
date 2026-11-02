"""
Capa de DOMINIO — Contexto: Reservas.

Agregado Reserva: un solicitante aparta un ítem para UN día y un rango de
horas de ese día (puede ser hoy o con antelación). La reserva reemplaza a la
"solicitud": si cumple las reglas se confirma sola (aprobación automática);
si el ítem es especial, la aprueba un supervisor.

Ciclo de vida:

    ACTIVA (lista de espera) ──se libera la franja──► CONFIRMADA o EN_ESPERA_SUPERVISOR
    EN_ESPERA_SUPERVISOR ──supervisor aprueba──► CONFIRMADA
                         ──supervisor rechaza──► RECHAZADA
    CONFIRMADA ──encargado entrega (Préstamos)──► ATENDIDA ──devolución──► FINALIZADA
    CONFIRMADA ──no la recoge a tiempo──► EXPIRADA
    ACTIVA / EN_ESPERA_SUPERVISOR / CONFIRMADA ──solicitante──► CANCELADA
    EN_ESPERA_SUPERVISOR / CONFIRMADA ──encargado (con motivo)──► ANULADA

Referencias a Item (Catálogo) y Cuenta (Identidad) por UUID, sin ForeignKey.
Los métodos cambian el estado en memoria; guardar es tarea del repositorio.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.common.choices import EstadoReserva
from apps.common.models import BaseModel

from .horario import minutos_del_dia

# Estados en los que la reserva "ocupa" su franja: nadie más puede reservar ese horario.
ESTADOS_QUE_OCUPAN = (
    EstadoReserva.EN_ESPERA_SUPERVISOR,
    EstadoReserva.CONFIRMADA,
    EstadoReserva.ATENDIDA,
)
# Reservas "vigentes" (aún no terminan): cuentan para el límite de la política.
ESTADOS_VIGENTES = (EstadoReserva.ACTIVA,) + ESTADOS_QUE_OCUPAN
# Reservas futuras que se anulan si el ítem queda fuera de servicio.
ESTADOS_ANULABLES = (EstadoReserva.ACTIVA, EstadoReserva.EN_ESPERA_SUPERVISOR, EstadoReserva.CONFIRMADA)


class Reserva(BaseModel):
    item_id = models.UUIDField("ítem", db_index=True)
    categoria_id = models.UUIDField("categoría", null=True, blank=True, db_index=True)
    solicitante_id = models.UUIDField("solicitante", db_index=True)

    fecha = models.DateField("fecha de uso")
    hora_inicio = models.TimeField("desde")
    hora_fin = models.TimeField("hasta")
    finalidad = models.TextField(blank=True)

    estado = models.CharField(max_length=25, choices=EstadoReserva.choices,
                              default=EstadoReserva.CONFIRMADA)
    posicion_en_cola = models.PositiveIntegerField(
        "posición en lista de espera", null=True, blank=True,
        help_text="Solo para reservas ACTIVAS (en lista de espera).",
    )
    aprobado_por_supervisor_id = models.UUIDField(null=True, blank=True)
    motivo = models.TextField(blank=True, help_text="Motivo de rechazo o anulación.")

    class Meta:
        app_label = "reservas"
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["fecha", "hora_inicio"]
        indexes = [models.Index(fields=["item_id", "fecha"], name="reserva_item_fecha_idx")]
        constraints = [
            # FIFO: en la lista de espera de un ítem no hay dos personas en la misma posición.
            models.UniqueConstraint(
                fields=["item_id", "posicion_en_cola"],
                condition=Q(estado="ACTIVA"),
                name="reserva_posicion_unica_por_item_activa",
            ),
            models.CheckConstraint(
                condition=Q(hora_fin__gt=models.F("hora_inicio")),
                name="reserva_hora_fin_mayor_que_inicio",
            ),
        ]

    def __str__(self):
        return f"Reserva {self.fecha} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M} · {self.get_estado_display()}"

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora de fin debe ser posterior a la hora de inicio.")

    @property
    def ocupa_franja(self):
        return self.estado in ESTADOS_QUE_OCUPAN

    def choca_con(self, desde, hasta, margen_min):
        """
        ¿El rango [desde, hasta) choca con esta reserva, contando el margen entre reservas?
        Con margen de 15: si esta es 9:00–9:15, entonces 9:15–10:00 choca y 9:30–10:00 no.
        """
        inicio_con_margen = minutos_del_dia(self.hora_inicio) - margen_min
        fin_con_margen = minutos_del_dia(self.hora_fin) + margen_min
        return inicio_con_margen < minutos_del_dia(hasta) and minutos_del_dia(desde) < fin_con_margen

    def se_cruza_con(self, desde, hasta):
        """¿Esta reserva se superpone con el rango [desde, hasta) del mismo día?"""
        return self.hora_inicio < hasta and desde < self.hora_fin

    def _pasar(self, nuevo, desde):
        """Cambia al estado `nuevo` solo si el estado actual está en `desde`."""
        if self.estado not in desde:
            raise ValidationError(
                f"No se puede pasar de «{self.get_estado_display()}» a «{EstadoReserva(nuevo).label}»."
            )
        self.estado = nuevo

    def confirmar(self):
        """Aprobación automática (o franja liberada para alguien de la lista de espera)."""
        self._pasar(EstadoReserva.CONFIRMADA, {EstadoReserva.ACTIVA})
        self.posicion_en_cola = None

    def enviar_a_supervisor(self):
        self._pasar(EstadoReserva.EN_ESPERA_SUPERVISOR, {EstadoReserva.ACTIVA})
        self.posicion_en_cola = None

    def aprobar_por_supervisor(self, supervisor_id):
        if supervisor_id == self.solicitante_id:
            raise ValidationError("No puedes aprobar tu propia reserva.")
        self._pasar(EstadoReserva.CONFIRMADA, {EstadoReserva.EN_ESPERA_SUPERVISOR})
        self.aprobado_por_supervisor_id = supervisor_id

    def rechazar_por_supervisor(self, supervisor_id, motivo):
        if supervisor_id == self.solicitante_id:
            raise ValidationError("No puedes revisar tu propia reserva.")
        if not motivo or not motivo.strip():
            raise ValidationError("Indica el motivo del rechazo.")
        self._pasar(EstadoReserva.RECHAZADA, {EstadoReserva.EN_ESPERA_SUPERVISOR})
        self.motivo = motivo.strip()

    def cancelar(self):
        self._pasar(EstadoReserva.CANCELADA, {
            EstadoReserva.ACTIVA, EstadoReserva.EN_ESPERA_SUPERVISOR, EstadoReserva.CONFIRMADA,
        })
        self.posicion_en_cola = None

    def anular(self, motivo):
        if not motivo or not motivo.strip():
            raise ValidationError("Indica el motivo de la anulación.")
        self._pasar(EstadoReserva.ANULADA, set(ESTADOS_ANULABLES))
        self.motivo = motivo.strip()
        self.posicion_en_cola = None

    def expirar(self):
        self._pasar(EstadoReserva.EXPIRADA, {
            EstadoReserva.ACTIVA, EstadoReserva.EN_ESPERA_SUPERVISOR, EstadoReserva.CONFIRMADA,
        })
        self.posicion_en_cola = None

    def marcar_atendida(self):
        """El encargado entregó el ítem (lo llama Préstamos)."""
        self._pasar(EstadoReserva.ATENDIDA, {EstadoReserva.CONFIRMADA})

    def finalizar(self):
        """El ítem fue devuelto (lo llama Préstamos)."""
        self._pasar(EstadoReserva.FINALIZADA, {EstadoReserva.ATENDIDA})

    def extender(self, nueva_hora_fin):
        """Renovación: alarga la franja (la validación de choques la hace el servicio)."""
        if self.estado != EstadoReserva.ATENDIDA:
            raise ValidationError("Solo se puede extender una reserva cuyo ítem ya fue entregado.")
        if nueva_hora_fin <= self.hora_fin:
            raise ValidationError("La nueva hora de fin debe ser posterior a la actual.")
        self.hora_fin = nueva_hora_fin
