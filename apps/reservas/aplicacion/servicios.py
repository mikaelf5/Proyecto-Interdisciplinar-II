"""
Capa de APLICACIÓN — IReservaServicio / ReservaServicioAplicacion.

Casos de uso de Reservas. Habla con otros módulos SOLO por sus servicios:
- Catálogo: datos del ítem, si es especial, otros ítems de la categoría.
- Identidad (puerto): ¿está habilitado?, ¿qué tipo de usuario es?
- Políticas (puerto): duración máxima, antelación y límites.
- Notificaciones: avisar cuando se libera una franja o cambia una reserva.

Lo que usa Catálogo: anular_reservas_del_item(...) cuando un ítem queda fuera de servicio.

Contrato con Préstamos (Marving):
    confirmadas_de_hoy(), marcar_atendida(reserva_id), franja_libre(...),
    extender(reserva_id, nueva_hora_fin), liberar(reserva_id)
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.choices import EstadoItem, EstadoReserva, TipoNotificacion

from ..dominio.excepciones import HorarioOcupado
from ..dominio.horario import HorarioAtencion
from ..dominio.models import Reserva
from ..dominio.servicios import AsignadorDeCola, CalculadoraDeHorarios, ReglasDeReserva
from ..infraestructura.repositorios import ReservaRepositorioImpl
from .dtos import ReservaDTO

FUERA_DE_SERVICIO = (EstadoItem.BAJA, EstadoItem.MANTENIMIENTO)


class IReservaServicio(ABC):
    """Lo que Reservas ofrece a las pantallas y a otros módulos."""

    @abstractmethod
    def crear(self, dto): ...

    @abstractmethod
    def anotarse_en_espera(self, dto): ...

    @abstractmethod
    def cancelar(self, reserva_id, solicitante_id): ...

    @abstractmethod
    def aprobar_supervisor(self, reserva_id, supervisor_id): ...

    @abstractmethod
    def rechazar_supervisor(self, reserva_id, supervisor_id, motivo): ...

    @abstractmethod
    def anular(self, reserva_id, motivo): ...

    @abstractmethod
    def expirar_reservas(self, ahora=None): ...

    @abstractmethod
    def anular_reservas_del_item(self, item_id, motivo): ...

    @abstractmethod
    def confirmadas_de_hoy(self): ...

    @abstractmethod
    def marcar_atendida(self, reserva_id): ...

    @abstractmethod
    def franja_libre(self, item_id, fecha, desde, hasta, excluir_reserva_id=None): ...

    @abstractmethod
    def extender(self, reserva_id, nueva_hora_fin): ...

    @abstractmethod
    def liberar(self, reserva_id): ...
    def liberar(self, reserva_id): ...

    @abstractmethod
    def finalizar_por_perdida(self, reserva_id): ...


class ReservaServicioAplicacion(IReservaServicio):
    def __init__(self, repositorio=None, catalogo=None, notificaciones=None, identidad=None,
                 politicas=None, horario=None, reloj=None):
        """Inyección de dependencias: en las pruebas se pasan versiones falsas."""
        self.repositorio = repositorio or ReservaRepositorioImpl()
        self.catalogo = catalogo or self._catalogo_por_defecto()
        self.notificaciones = notificaciones or self._notificaciones_por_defecto()
        self.identidad = identidad or self._identidad_por_defecto()
        self.politicas = politicas or self._politicas_por_defecto()
        self.horario = horario or HorarioAtencion.desde_settings()
        self.reloj = reloj or timezone.localtime
        self.asignador = AsignadorDeCola()
        self.reglas = ReglasDeReserva(self.horario)
        self.calculadora = CalculadoraDeHorarios(self.horario)

    # Los otros módulos se importan aquí adentro para no crear importaciones circulares.
    @staticmethod
    def _catalogo_por_defecto():
        from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
        return CatalogoServicioAplicacion()

    @staticmethod
    def _notificaciones_por_defecto():
        from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
        return NotificacionServicioAplicacion()

    @staticmethod
    def _identidad_por_defecto():
        from ..infraestructura.adaptadores import IdentidadAdaptador
        return IdentidadAdaptador()

    @staticmethod
    def _politicas_por_defecto():
        from ..infraestructura.adaptadores import PoliticasAdaptador
        return PoliticasAdaptador()

    # Casos de uso del SOLICITANTE

    @transaction.atomic
    def crear(self, dto):
        """Botón "Reservar". Si cumple las reglas se aprueba sola (o va al supervisor)."""
        self.expirar_reservas()                    # libera las franjas de quien no vino
        item = self._item_solicitado(dto)
        politica = self._validar_reglas(dto, item.categoria_id)
        self.repositorio.bloquear_item(item.id)
        self._verificar_franja_libre(item, dto)
        self._verificar_limites(politica, item, dto)
        reserva = self._nueva_reserva(item, dto)
        self._aprobar_automaticamente(reserva, item.categoria_es_especial)
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def anotarse_en_espera(self, dto):
        """Botón "Avisarme si se libera": entra a la lista de espera FIFO (RF-F2)."""
        if not dto.item_id:
            raise ValidationError("Indica el ítem para anotarte en su lista de espera.")
        self.expirar_reservas()
        item = self._item_reservable(dto.item_id)
        politica = self._validar_reglas(dto, item.categoria_id)
        self.repositorio.bloquear_item(item.id)
        self._verificar_que_puede_esperar(item, dto)
        self._verificar_limites(politica, item, dto)  # la lista de espera también cuenta
        reserva = self._nueva_reserva(item, dto)
        reserva.posicion_en_cola = self.asignador.posicion_para_nueva(self.repositorio.cola_de(item.id))
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def cancelar(self, reserva_id, solicitante_id):
        """Botón "Cancelar" de Mis reservas. Solo el dueño puede cancelar."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        if reserva.solicitante_id != solicitante_id:
            raise ValidationError("Solo puedes cancelar tus propias reservas.")
        ocupaba_franja = reserva.ocupa_franja
        reserva.cancelar()
        self.repositorio.guardar(reserva)
        if ocupaba_franja:
            self._pasar_turno_en(reserva.item_id, reserva.fecha)
        return ReservaDTO.desde(reserva)

    # Casos de uso del SUPERVISOR y del ENCARGADO

    @transaction.atomic
    def aprobar_supervisor(self, reserva_id, supervisor_id):
        """Botón "Aprobar" de la bandeja del supervisor (ítems especiales, RF-D5)."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        if self._ya_empezo(reserva, self.reloj()):
            raise ValidationError("El horario de esta reserva ya empezó: ya no se puede aprobar.")
        reserva.aprobar_por_supervisor(supervisor_id)
        self.repositorio.guardar(reserva)
        self._avisar(reserva, f"Tu reserva de {self._describir(reserva)} fue aprobada por el supervisor.")
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def rechazar_supervisor(self, reserva_id, supervisor_id, motivo):
        """Botón "Rechazar" de la bandeja del supervisor (exige motivo, RF-D2)."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.rechazar_por_supervisor(supervisor_id, motivo)
        self.repositorio.guardar(reserva)
        self._avisar(reserva, f"Tu reserva de {self._describir(reserva)} fue rechazada. Motivo: {reserva.motivo}")
        self._pasar_turno_en(reserva.item_id, reserva.fecha)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def anular(self, reserva_id, motivo):
        """Botón "Anular" de la agenda (encargado). Exige motivo y avisa al solicitante."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.anular(motivo)
        self.repositorio.guardar(reserva)
        self._avisar(reserva, f"Tu reserva de {self._describir(reserva)} fue anulada. Motivo: {reserva.motivo}")
        self._pasar_turno_en(reserva.item_id, reserva.fecha)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def expirar_reservas(self, ahora=None):
        """Comando `expirar_reservas`: vence las reservas no recogidas y pasa el turno."""
        ahora = ahora or self.reloj()
        expiradas, franjas_liberadas = [], set()
        for reserva in self.repositorio.pendientes_hasta(ahora.date()):
            if not self._debe_expirar(reserva, ahora):
                continue
            if reserva.ocupa_franja:
                franjas_liberadas.add((reserva.item_id, reserva.fecha))
            reserva.expirar()
            self.repositorio.guardar(reserva)
            expiradas.append(ReservaDTO.desde(reserva))
        for item_id, fecha in franjas_liberadas:
            self._pasar_turno_en(item_id, fecha, ahora)
        return expiradas

    @transaction.atomic
    def anular_reservas_del_item(self, item_id, motivo):
        """Catálogo la llama al marcar un ítem dañado o darlo de baja: anula y avisa a cada uno."""
        anuladas = self.repositorio.futuras_del_item(item_id, self.reloj().date())
        for reserva in anuladas:
            reserva.anular(motivo)
            self.repositorio.guardar(reserva)
            self._avisar(reserva, f"Tu reserva de {self._describir(reserva)} fue anulada. Motivo: {motivo}")
        return len(anuladas)

    # Contrato con PRÉSTAMOS

    def confirmadas_de_hoy(self):
        """Reservas que el encargado puede entregar hoy."""
        return [ReservaDTO.desde(r) for r in self.repositorio.confirmadas_del_dia(self.reloj().date())]

    @transaction.atomic
    def marcar_atendida(self, reserva_id):
        """Préstamos la llama al ENTREGAR el ítem."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        if reserva.fecha != self.reloj().date():
            raise ValidationError("Esta reserva es para otro día.")
        reserva.marcar_atendida()
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    def franja_libre(self, item_id, fecha, desde, hasta, excluir_reserva_id=None):
        ocupadas = self.repositorio.ocupadas_de(item_id, fecha, excluir_id=excluir_reserva_id)
        return not any(self._choca(r, desde, hasta) for r in ocupadas)

    @transaction.atomic
    def extender(self, reserva_id, nueva_hora_fin):
        """Préstamos la llama al RENOVAR: alarga la franja si nadie reservó después."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        if nueva_hora_fin > self.horario.cierre:
            raise ValidationError(f"No se puede pasar de la hora de cierre ({self.horario.cierre:%H:%M}).")
        self.repositorio.bloquear_item(reserva.item_id)
        if not self.franja_libre(reserva.item_id, reserva.fecha, reserva.hora_fin, nueva_hora_fin,
                                 excluir_reserva_id=reserva.id):
            raise ValidationError("No se puede renovar: la franja siguiente ya está reservada.")
        reserva.extender(nueva_hora_fin)
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)

    @transaction.atomic
    def liberar(self, reserva_id):
        """Préstamos la llama en la DEVOLUCIÓN: cierra la reserva y avanza la lista de espera."""
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.finalizar()
        self.repositorio.guardar(reserva)
        self._pasar_turno_en(reserva.item_id, reserva.fecha)
        return ReservaDTO.desde(reserva)


    @transaction.atomic
    def finalizar_por_perdida(self, reserva_id):
        reserva = self.repositorio.buscar_por_id(reserva_id)
        reserva.finalizar()
        self.repositorio.guardar(reserva)
        return ReservaDTO.desde(reserva)
    # Consultas para las pantallas

    def obtener(self, reserva_id):
        return ReservaDTO.desde(self.repositorio.buscar_por_id(reserva_id))

    def mis_reservas(self, solicitante_id):
        """Pantalla "Mis reservas"."""
        return [ReservaDTO.desde(r) for r in self.repositorio.de_solicitante(solicitante_id)]

    def en_espera_supervisor(self):
        """Pantalla "Bandeja del supervisor"."""
        return [ReservaDTO.desde(r) for r in self.repositorio.en_espera_supervisor()]

    def horarios_libres(self, item_id, fecha):
        return self.calculadora.libres(fecha, self.repositorio.ocupadas_de(item_id, fecha), self.reloj())

    def agenda(self, item_id, fecha):
        """Pantalla "Agenda": franjas ocupadas, lista de espera y huecos libres de un día."""
        ocupadas = self.repositorio.ocupadas_de(item_id, fecha)
        return {
            "ocupadas": [ReservaDTO.desde(r) for r in ocupadas],
            "cola": [ReservaDTO.desde(r) for r in self.repositorio.cola_de(item_id, fecha)],
            "libres": self.calculadora.libres(fecha, ocupadas, self.reloj()),
            "atiende": self.horario.atiende(fecha),
        }

    # Pasos de crear() y anotarse_en_espera()

    def _item_solicitado(self, dto):
        if dto.item_id:
            return self._item_reservable(dto.item_id)
        if dto.categoria_id:
            return self._item_libre_de_categoria(dto)
        raise ValidationError("Indica el ítem o la categoría que quieres reservar.")

    def _item_reservable(self, item_id):
        item = self.catalogo.obtener_item(item_id)
        if item.estado in FUERA_DE_SERVICIO:
            raise ValidationError(f"{item.codigo} está fuera de servicio ({item.estado_display.lower()}).")
        return item

    def _item_libre_de_categoria(self, dto):
        for item in self._items_en_servicio(dto.categoria_id):
            if self.franja_libre(item.id, dto.fecha, dto.hora_inicio, dto.hora_fin):
                return item
        raise ValidationError("No hay ítems libres de esa categoría en ese horario. Prueba otro horario.")

    def _items_en_servicio(self, categoria_id):
        from apps.catalogo.aplicacion.dtos import FiltrosItem
        todos = self.catalogo.buscar_items(FiltrosItem(categoria_id=categoria_id))
        return [item for item in todos if item.estado not in FUERA_DE_SERVICIO]

    def _validar_reglas(self, dto, categoria_id):
        """Habilitación (Identidad) + política (Políticas) + horario. Devuelve la política."""
        self._verificar_habilitacion(dto.solicitante_id)
        politica = self._politica_de(dto.solicitante_id, categoria_id)
        self.reglas.validar(dto.fecha, dto.hora_inicio, dto.hora_fin, self.reloj(), politica)
        return politica

    def _verificar_habilitacion(self, solicitante_id):
        habilitado, mensaje = self.identidad.habilitacion(solicitante_id)
        if not habilitado:
            raise ValidationError(f"No estás habilitado para reservar. {mensaje}")

    def _politica_de(self, solicitante_id, categoria_id):
        tipo_usuario = self.identidad.tipo_usuario(solicitante_id)
        politica = self.politicas.politica_para(categoria_id, tipo_usuario) if tipo_usuario else None
        if politica is None:
            raise ValidationError("No hay una política de préstamo para esta categoría y tu tipo de "
                                  "usuario. Consulta con el administrador.")
        return politica

    def _verificar_franja_libre(self, item, dto):
        """Franja exclusiva: si choca, se rechaza ofreciendo horarios libres y otros ítems."""
        ocupadas = self.repositorio.ocupadas_de(item.id, dto.fecha)
        choque = next(
            (r for r in ocupadas if self._choca(r, dto.hora_inicio, dto.hora_fin)),
            None
        )

        if choque:
            # Buscar otros ítems de la misma categoría que estén disponibles.
            alternativos = [
                otro for otro in self._items_en_servicio(item.categoria_id)
                if otro.id != item.id
                   and self.franja_libre(
                    otro.id,
                    dto.fecha,
                    dto.hora_inicio,
                    dto.hora_fin
                )
            ]

            raise HorarioOcupado(
                f"{item.codigo} ({item.nombre}) ya está reservado el {choque.fecha:%d/%m/%Y} "
                f"de {choque.hora_inicio:%H:%M} a {choque.hora_fin:%H:%M}. Entre reservas se dejan "
                f"{self.horario.margen_entre_reservas_min} minutos para recibir y revisar el ítem. "
                f"Elige otro horario.",
                ocupada=ReservaDTO.desde(choque),
                horarios_libres=self.calculadora.libres(
                    dto.fecha, ocupadas, self.reloj()
                ),
                alternativos=alternativos,
            )

    def _verificar_limites(self, politica, item, dto):
        """Máximo de reservas vigentes en total y por clase de ítem (ej. 1 especial a la vez)."""
        hoy = self.reloj().date()
        mismo_tipo = self._categorias_especiales() if item.categoria_es_especial else [item.categoria_id]
        self.reglas.validar_limites(
            politica,
            vigentes_total=self.repositorio.vigentes_de(dto.solicitante_id, hoy),
            vigentes_mismo_tipo=self.repositorio.vigentes_de(dto.solicitante_id, hoy, categoria_ids=mismo_tipo),
            es_especial=item.categoria_es_especial,
        )

    def _categorias_especiales(self):
        return [categoria.id for categoria in self.catalogo.listar_categorias() if categoria.es_especial]

    def _verificar_que_puede_esperar(self, item, dto):
        ocupadas = [r for r in self.repositorio.ocupadas_de(item.id, dto.fecha)
                    if self._choca(r, dto.hora_inicio, dto.hora_fin)]
        if not ocupadas:
            raise ValidationError("Ese horario está libre: puedes reservarlo directamente.")
        if any(r.solicitante_id == dto.solicitante_id for r in ocupadas):
            raise ValidationError("Ya tienes una reserva en ese horario.")
        en_espera = self.repositorio.cola_de(item.id, dto.fecha)
        if any(r.solicitante_id == dto.solicitante_id and r.se_cruza_con(dto.hora_inicio, dto.hora_fin)
               for r in en_espera):
            raise ValidationError("Ya estás en la lista de espera de ese horario.")

    @staticmethod
    def _nueva_reserva(item, dto):
        return Reserva(
            item_id=item.id, categoria_id=item.categoria_id, solicitante_id=dto.solicitante_id,
            fecha=dto.fecha, hora_inicio=dto.hora_inicio, hora_fin=dto.hora_fin,
            finalidad=(dto.finalidad or "").strip(), estado=EstadoReserva.ACTIVA,
        )

    @staticmethod
    def _aprobar_automaticamente(reserva, es_especial):
        """Aprobación automática; los ítems especiales los revisa un supervisor (RF-D5)."""
        if es_especial:
            reserva.enviar_a_supervisor()
        else:
            reserva.confirmar()

    # Lista de espera: pasar el turno cuando se libera una franja (RF-F2, RF-H3)

    def _pasar_turno_en(self, item_id, fecha, ahora=None):
        """En orden FIFO, da la franja a quien ahora sí entra y le avisa."""
        self.repositorio.bloquear_item(item_id)
        ahora = ahora or self.reloj()
        ocupadas = self.repositorio.ocupadas_de(item_id, fecha)
        es_especial = self.catalogo.es_especial(item_id=item_id)
        for reserva in self.asignador.en_orden(self.repositorio.cola_de(item_id, fecha)):
            if self._ya_empezo(reserva, ahora):
                reserva.expirar()
            elif self._franja_sigue_tomada(reserva, ocupadas):
                continue
            else:
                self._aprobar_automaticamente(reserva, es_especial)
                ocupadas.append(reserva)
                self._avisar_turno(reserva, es_especial)
            self.repositorio.guardar(reserva)

    def _franja_sigue_tomada(self, reserva, ocupadas):
        return any(self._choca(o, reserva.hora_inicio, reserva.hora_fin) for o in ocupadas)

    def _choca(self, reserva, desde, hasta):
        """Única regla de choque de horarios: superposición + margen entre reservas (15 min)."""
        return reserva.choca_con(desde, hasta, self.horario.margen_entre_reservas_min)

    def _avisar_turno(self, reserva, es_especial):
        falta_supervisor = " Falta la aprobación del supervisor." if es_especial else ""
        self._avisar(reserva, f"Se liberó {self._describir(reserva)} y quedó reservado para ti.{falta_supervisor}")

    # Expiración

    def _debe_expirar(self, reserva, ahora):
        """Confirmada: 15 min de tolerancia para recogerla. En espera: en cuanto empieza su horario."""
        limite = self._inicio(reserva)
        if reserva.estado == EstadoReserva.CONFIRMADA:
            limite += timedelta(minutes=self.horario.tolerancia_min)
        return ahora >= limite

    def _ya_empezo(self, reserva, ahora):
        return self._inicio(reserva) <= ahora

    @staticmethod
    def _inicio(reserva):
        inicio = datetime.combine(reserva.fecha, reserva.hora_inicio)
        return timezone.make_aware(inicio, timezone.get_current_timezone())

    # Avisos

    def _describir(self, reserva):
        """'LIB-001 para el 02/11/2026 de 10:00 a 12:00' (para los mensajes)."""
        return f"{self._codigo(reserva.item_id)} para el {reserva.fecha:%d/%m/%Y} " \
               f"de {reserva.hora_inicio:%H:%M} a {reserva.hora_fin:%H:%M}"

    def _codigo(self, item_id):
        try:
            return self.catalogo.obtener_item(item_id).codigo
        except ValidationError:
            return "el ítem"

    def _avisar(self, reserva, mensaje):
        self.notificaciones.enviar(reserva.solicitante_id, TipoNotificacion.DISPONIBILIDAD_RESERVA, mensaje)
