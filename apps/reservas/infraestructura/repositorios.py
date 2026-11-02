"""Capa de INFRAESTRUCTURA — ReservaRepositorioImpl (Django ORM + PostgreSQL)."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import connection

from apps.common.choices import EstadoReserva

from ..dominio.models import ESTADOS_QUE_OCUPAN, Reserva
from ..dominio.repositorios import IReservaRepositorio


class ReservaRepositorioImpl(IReservaRepositorio):
    def guardar(self, reserva):
        reserva.full_clean()  # valida campos + restricciones (posición única, fin > inicio)
        reserva.save()
        return reserva

    def buscar_por_id(self, reserva_id):
        try:
            return Reserva.objects.get(pk=reserva_id)
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise ValidationError("La reserva no existe.")

    def bloquear_item(self, item_id):
        # Candado de PostgreSQL que dura hasta el final de la transacción: si dos
        # personas reservan el mismo ítem a la vez, la segunda espera a la primera.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [str(item_id)])

    def ocupadas_de(self, item_id, fecha, excluir_id=None):
        qs = Reserva.objects.filter(item_id=item_id, fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN)
        if excluir_id:
            qs = qs.exclude(pk=excluir_id)
        return list(qs.order_by("hora_inicio"))

    def cola_de(self, item_id, fecha=None):
        qs = Reserva.objects.filter(item_id=item_id, estado=EstadoReserva.ACTIVA)
        if fecha:
            qs = qs.filter(fecha=fecha)
        return list(qs.order_by("posicion_en_cola"))

    def de_solicitante(self, solicitante_id):
        return list(Reserva.objects.filter(solicitante_id=solicitante_id)
                    .order_by("-fecha", "-hora_inicio"))

    def simultaneas_de(self, solicitante_id, fecha, desde, hasta, categoria_id=None):
        qs = Reserva.objects.filter(
            solicitante_id=solicitante_id, fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN,
            hora_inicio__lt=hasta, hora_fin__gt=desde,   # se cruzan
        )
        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)
        return qs.count()

    def en_espera_supervisor(self):
        return list(Reserva.objects.filter(estado=EstadoReserva.EN_ESPERA_SUPERVISOR)
                    .order_by("fecha", "hora_inicio"))

    def confirmadas_del_dia(self, fecha):
        return list(Reserva.objects.filter(estado=EstadoReserva.CONFIRMADA, fecha=fecha)
                    .order_by("hora_inicio"))

    def pendientes_hasta(self, fecha):
        return list(Reserva.objects.filter(
            fecha__lte=fecha,
            estado__in=[EstadoReserva.ACTIVA, EstadoReserva.EN_ESPERA_SUPERVISOR, EstadoReserva.CONFIRMADA],
        ).order_by("fecha", "hora_inicio"))
