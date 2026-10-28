"""
Capa de APLICACIÓN — IReservaServicio / ReservaServicioAplicacion (PDF).

Coordina con otros contextos SOLO a través de sus servicios de aplicación:
- Catálogo: ¿el ítem está disponible?
- Notificaciones: avisar al siguiente de la cola.
"""
from abc import ABC, abstractmethod
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.choices import TipoNotificacion

from ..dominio.models import Reserva
from ..dominio.servicios import AsignadorDeCola
from ..infraestructura.repositorios import ReservaRepositorioImpl
from .dtos import ReservaDTO


class IReservaServicio(ABC):
    @abstractmethod
    def crear(self, item_id, solicitante_id): ...

    @abstractmethod
    def confirmar(self, reserva_id): ...

    @abstractmethod
    def cancelar(self, reserva_id): ...

    @abstractmethod
    def asignar_siguiente(self, item_id): ...

    @abstractmethod
    def expirar_reservas(self, hoy=None): ...

    @abstractmethod
    def lista_espera(self, item_id): ...


class ReservaServicioAplicacion(IReservaServicio):
    def __init__(self, repositorio=None, catalogo=None, notificaciones=None):
        self.repositorio = repositorio or ReservaRepositorioImpl()
        self.asignador = AsignadorDeCola()
        # Servicios de otros contextos (se importan aquí para no crear dependencias circulares)
        if catalogo is None:
            from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
            catalogo = CatalogoServicioAplicacion()
        if notificaciones is None:
            from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
            notificaciones = NotificacionServicioAplicacion()
        self.catalogo = catalogo
        self.notificaciones = notificaciones

    @transaction.atomic
    def crear(self, item_id, solicitante_id):
        """Pone al solicitante al final de la cola del ítem."""
        item = self.catalogo.obtener_item(item_id)
        if item.esta_disponible:
            raise ValidationError("El ítem está disponible: puedes solicitarlo directamente, sin reservar.")
        if item.estado == "BAJA":
            raise ValidationError("El ítem fue dado de baja y no se puede reservar.")

        cola = self.repositorio.cola_de(item_id, bloquear=True)
        if any(r.solicitante_id == solicitante_id for r in cola):
            raise ValidationError("Ya tienes una reserva activa para este ítem.")

        reserva = Reserva(
            item_id=item_id,
            solicitante_id=solicitante_id,
            posicion_en_cola=self.asignador.posicion_para_nueva(cola),
        )
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    def siguiente_posicion(self, item_id):
        return self.asignador.posicion_para_nueva(self.repositorio.cola_de(item_id))

    @transaction.atomic
    def confirmar(self, reserva_id):
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.confirmar()
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def cancelar(self, reserva_id):
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.cancelar()
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    def expirar(self, reserva_id):
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.expirar()
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def asignar_siguiente(self, item_id):
        """
        El ítem se liberó: confirma la primera reserva de la cola y le avisa.
        Lo llamará Circulación cuando registre una devolución.
        """
        siguiente = self.asignador.siguiente(self.repositorio.cola_de(item_id, bloquear=True))
        if siguiente is None:
            return None
        siguiente.confirmar()
        self.repositorio.guardar(siguiente)
        item = self.catalogo.obtener_item(item_id)
        self.notificaciones.enviar(
            siguiente.solicitante_id,
            TipoNotificacion.DISPONIBILIDAD_RESERVA,
            f"El ítem {item.codigo} ({item.nombre}) ya está disponible para ti. Acércate a recogerlo.",
        )
        return ReservaDTO.desde(siguiente)

    @transaction.atomic
    def expirar_reservas(self, hoy=None, dias_para_recoger=2):
        """
        Expira las reservas CONFIRMADAS que no se recogieron a tiempo y pasa
        el turno al siguiente de la cola. (Los días saldrán de Políticas más adelante.)
        """
        limite = (hoy or timezone.now()) - timedelta(days=dias_para_recoger)
        expiradas = []
        for reserva in self.repositorio.confirmadas_antes_de(limite):
            reserva.expirar()
            self.repositorio.guardar(reserva)
            expiradas.append(ReservaDTO.desde(reserva))
            self.asignar_siguiente(reserva.item_id)
        return expiradas

    def lista_espera(self, item_id):
        """ReservaController.listaEspera(request, itemId)"""
        return [ReservaDTO.desde(r) for r in self.repositorio.cola_de(item_id)]

    def mis_reservas(self, solicitante_id):
        return [ReservaDTO.desde(r) for r in self.repositorio.de_solicitante(solicitante_id)]
