"""Capa de INFRAESTRUCTURA — ReservaRepositorioImpl (Django ORM + PostgreSQL)."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.common.choices import EstadoReserva

from ..dominio.models import Reserva
from ..dominio.repositorios import IReservaRepositorio


class ReservaRepositorioImpl(IReservaRepositorio):
    def guardar(self, reserva):
        reserva.full_clean()  # incluye las restricciones únicas de la cola
        reserva.save()

    def buscar_por_id(self, reserva_id):
        try:
            return Reserva.objects.get(pk=reserva_id)
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise ValidationError("La reserva no existe.")

    def cola_de(self, item_id, bloquear=False):
        qs = Reserva.objects.filter(item_id=item_id, estado=EstadoReserva.ACTIVA).order_by("posicion_en_cola")
        if bloquear:
            # Dentro de una transacción: evita que dos personas tomen la misma posición a la vez.
            qs = qs.select_for_update()
        return list(qs)

    def de_solicitante(self, solicitante_id):
        return list(Reserva.objects.filter(solicitante_id=solicitante_id).order_by("-creado_en"))

    def confirmadas_antes_de(self, fecha_hora):
        return list(Reserva.objects.filter(estado=EstadoReserva.CONFIRMADA, actualizado_en__lt=fecha_hora))
