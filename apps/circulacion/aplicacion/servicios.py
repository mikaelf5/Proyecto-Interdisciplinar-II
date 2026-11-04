"""Casos de uso de Circulación. Las dependencias externas se inyectan."""
from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.common.choices import (
    EstadoPrestamo,
    TipoGarantia,
    TipoNotificacion,
    EstadoReserva,
)

from apps.circulacion.dominio.models import Prestamo
from apps.circulacion.aplicacion.dtos import PrestamoDTO

class IPrestamoServicio(ABC):
    @abstractmethod
    def registrar_entrega(self, dto): ...
    @abstractmethod
    def renovar(self, id): ...
    @abstractmethod
    def registrar_devolucion(self, dto): ...
    @abstractmethod
    def listar_vencidos(self): ...

    @abstractmethod
    def historial_de(self, solicitante_id): ...
    @abstractmethod
    def cerrar_por_perdida(self, prestamo_id): ...

    @abstractmethod
    def buscar_vencidos(self, solicitante_id=None, item_id=None): ...


class PrestamoServicioAplicacion(IPrestamoServicio):
    def __init__(self, prestamo_repositorio, reservas=None,
                 elegibilidad=None, catalogo=None, politica_servicio=None,
                 auditoria=None, condicion_servicio=None, identidad=None,
                 notificaciones=None):
        self.repositorio = prestamo_repositorio
        self.reservas = reservas
        self.elegibilidad = elegibilidad
        self.catalogo = catalogo
        self.politicas = politica_servicio
        self.auditoria = auditoria
        self.condiciones = condicion_servicio
        self.identidad = identidad
        self.notificaciones = notificaciones

    def _prestamo(self, prestamo_id):
        prestamo = self.repositorio.buscar_por_id(prestamo_id)

        if prestamo is None:
            raise ValidationError("No existe el préstamo solicitado.")

        return prestamo
    def _registrar_condicion(self, item_id, prestamo_id, responsable_id,
                            momento, fecha, descripcion, foto=""):
        """Usa el contrato de Catálogo sin importar su rama al cargar este módulo."""
        try:
            from apps.catalogo.aplicacion.dtos import NuevaCondicionDTO
        except ImportError as exc:
            raise ValidationError(
                "El DTO de condiciones de Catálogo aún no está integrado."
            ) from exc
        servicio = self.condiciones if self.condiciones is not None else self.catalogo
        if servicio is None:
            raise ValidationError("Falta el servicio de condiciones de Catálogo.")
        condicion = NuevaCondicionDTO(
            item_id=item_id, prestamo_id=prestamo_id,
            responsable_id=responsable_id, momento=momento,
            fecha=timezone.localtime(fecha).date(),
            descripcion=descripcion, foto=foto,
        )
        return servicio.registrar_condicion(condicion)

    def _politica(self, prestamo):
        # Obtener información del ítem.
        item = self.catalogo.obtener_item(prestamo.item_id)

        # Obtener el tipo de usuario.
        tipo_usuario = self.identidad.tipo_usuario_de(
            prestamo.solicitante_id
        )

        if not tipo_usuario:
            raise ValidationError(
                "No se pudo determinar el tipo de usuario del solicitante."
            )

        # Buscar la política según categoría y tipo de usuario.
        politica = self.politicas.politica_para(
            item.categoria_id,
            tipo_usuario
        )

        if politica is None:
            raise ValidationError(
                "No existe una política aplicable."
            )

        return politica

    @transaction.atomic
    def registrar_entrega(self, dto):
        # Verificar que las dependencias estén integradas.
        if not all([
            self.reservas,
            self.catalogo,
            self.auditoria,
            self.identidad,
            self.politicas,
        ]):
            raise ValidationError(
                "Faltan dependencias para registrar la entrega del préstamo."
            )

        # Verificar aceptación de términos.
        if not dto.terminos_aceptados:
            raise ValidationError("Debes aceptar los términos del préstamo.")
        # Verificar descripción de la condición física.
        if not dto.descripcion_condicion.strip():
            raise ValidationError(
                "Debes describir la condición física del artículo."
            )
        # Validar garantía.
        if dto.garantia_tipo not in TipoGarantia.values:
            raise ValidationError("Selecciona un tipo de garantía válido.")

        if dto.garantia_tipo == TipoGarantia.OTRO and not dto.garantia_detalle.strip():
            raise ValidationError("Describe la garantía seleccionada.")

        # Buscar la reserva.
        reserva = self.reservas.obtener(dto.reserva_id)

        if reserva.estado != EstadoReserva.CONFIRMADA:
            raise ValidationError(
                "Solo se pueden entregar ítems con reservas confirmadas."
            )

        # Verificar habilitación del solicitante.
        resultado = self.identidad.consultar_habilitacion(
            reserva.solicitante_id
        )

        if not resultado.habilitado:
            raise ValidationError(
                f"El solicitante no está habilitado. {resultado.mensaje}"
            )

        # Verificar disponibilidad del ítem.
        if not self.catalogo.esta_disponible(reserva.item_id):
            raise ValidationError("El ítem no está disponible para préstamo.")

        # Evitar dos préstamos abiertos para el mismo ítem.
        if self.repositorio.existe_abierto_para_item(reserva.item_id):
            raise ValidationError("El ítem ya tiene un préstamo abierto.")

        # Obtener política y calcular vencimiento.
        tipo_usuario = self.identidad.tipo_usuario_de(
            reserva.solicitante_id
        )

        if not tipo_usuario:
            raise ValidationError(
                "No se pudo determinar el tipo de usuario del solicitante."
            )

        politica = self.politicas.politica_para(
            reserva.categoria_id,
            tipo_usuario
        )

        if politica is None:
            raise ValidationError("No existe una política aplicable.")

        # La devolución debe realizarse al terminar la reserva.
        fecha_vencimiento = timezone.make_aware(
            datetime.combine(reserva.fecha, reserva.hora_fin),
            timezone.get_current_timezone()
        )

        ahora = timezone.localtime()

        if fecha_vencimiento <= ahora:
            raise ValidationError("El horario de esta reserva ya terminó.")

        # Marcar la reserva como atendida.
        self.reservas.marcar_atendida(dto.reserva_id)

        # Registrar el préstamo.
        prestamo = Prestamo(
            item_id=reserva.item_id,
            solicitante_id=reserva.solicitante_id,
            reserva_id=reserva.id,
            encargado_entrega_id=dto.encargado_id,
            garantia_tipo=dto.garantia_tipo,
            garantia_detalle=dto.garantia_detalle,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=fecha_vencimiento,
            estado=EstadoPrestamo.ACTIVO,
        )

        try:
            with transaction.atomic():
                self.repositorio.guardar(prestamo)

        except IntegrityError as exc:
            causa = exc.__cause__
            nombre_restriccion = getattr(
                getattr(causa, "diag", None),
                "constraint_name",
                None
            )

            if nombre_restriccion == "unique_prestamo_abierto_por_item":
                raise ValidationError(
                    "El ítem ya tiene un préstamo abierto."
                ) from exc

            raise

        # Cambiar el estado del ítem en Catálogo.
        self.catalogo.marcar_prestado(reserva.item_id)

        # Registrar la condición física de entrega.
        self._registrar_condicion(
            item_id=reserva.item_id,
            prestamo_id=prestamo.id,
            responsable_id=dto.encargado_id,
            momento="ENTREGA",
            fecha=ahora,
            descripcion=dto.descripcion_condicion
        )

        # Registrar auditoría.
        self.auditoria.registrar(
            actor_id=dto.encargado_id,
            accion="ENTREGA_PRESTAMO",
            entidad="Prestamo",
            entidad_id=prestamo.id,
            motivo=f"Entrega del préstamo asociado a la reserva {reserva.id}."
        )

        return PrestamoDTO.desde_modelo(prestamo)

    @transaction.atomic
    def renovar(self, id, nueva_hora_fin):
        prestamo = self._prestamo(id)

        ahora = timezone.localtime()

        if ahora.time() >= time(20, 0):
            raise ValidationError(
                "Las renovaciones solo se permiten antes de las 20:00."
            )

        politica = self._politica(prestamo)

        if prestamo.estado != EstadoPrestamo.ACTIVO:
            raise ValidationError("Este préstamo no está activo.")

        if prestamo.esta_vencido():
            raise ValidationError("No puedes renovar un préstamo vencido.")

        reserva = self.reservas.obtener(prestamo.reserva_id)

        if nueva_hora_fin <= reserva.hora_fin:
            raise ValidationError(
                "La nueva hora debe ser posterior al vencimiento actual."
            )

        if nueva_hora_fin > time(20, 0):
            raise ValidationError(
                "La devolución no puede superar las 20:00."
            )

        # La renovación debe permanecer en el mismo día.
        if timezone.localtime(prestamo.fecha_vencimiento).date() != reserva.fecha:
            raise ValidationError(
                "La renovación no puede extenderse a un día diferente."
            )

        # Calcular las horas adicionales solicitadas.
        nueva_fecha = timezone.make_aware(
            datetime.combine(reserva.fecha, nueva_hora_fin),
            timezone.get_current_timezone()
        )

        duracion = nueva_fecha - prestamo.fecha_vencimiento

        if duracion.total_seconds() > politica.duracion_maxima * 3600:
            raise ValidationError(
                "La renovación supera la duración máxima permitida."
            )

        # Actualizar el préstamo y validar el límite de renovaciones.
        prestamo.renovar(nueva_fecha, politica)

        # Comprobar disponibilidad y extender la reserva.
        self.reservas.extender(
            prestamo.reserva_id,
            nueva_hora_fin
        )

        self.repositorio.guardar(prestamo)

        self.auditoria.registrar(
            actor_id=prestamo.solicitante_id,
            accion="RENOVACION_PRESTAMO",
            entidad="Prestamo",
            entidad_id=prestamo.id,
            motivo=f"Nuevo vencimiento: {prestamo.fecha_vencimiento}."
        )

        return PrestamoDTO.desde_modelo(prestamo)

    @transaction.atomic
    def registrar_devolucion(self, dto):
        # Verificar dependencias necesarias.
        if self.catalogo is None or self.reservas is None:
            raise ValidationError(
                "Se requiere Catálogo y Reservas para registrar la devolución."
            )

        if not dto.descripcion_condicion.strip():
            raise ValidationError(
                "Debe registrar la condición física del ítem."
            )

        # Buscar el préstamo.
        prestamo = self._prestamo(dto.prestamo_id)

        if prestamo.estado not in (
                EstadoPrestamo.ACTIVO,
                EstadoPrestamo.VENCIDO
        ):
            raise ValidationError("El préstamo no está abierto.")

        ahora = timezone.now()

        # Registrar la condición física en Catálogo.
        self._registrar_condicion(
            prestamo.item_id,
            prestamo.id,
            dto.encargado_id,
            "DEVOLUCION",
            ahora,
            dto.descripcion_condicion,
            dto.foto
        )

        # Cerrar el préstamo.
        prestamo.registrar_devolucion(
            encargado_id=dto.encargado_id,
            fecha=ahora
        )

        # Registrar si el encargado devolvió la garantía al usuario.
        prestamo.garantia_devuelta = dto.garantia_devuelta
        prestamo.save(
            update_fields=["garantia_devuelta", "actualizado_en"]
        )

        # Actualizar el estado del ítem según su condición.
        if dto.item_daniado:
            self.catalogo.marcar_daniado(
                prestamo.item_id,
                dto.descripcion_condicion
            )

            # Notificar al solicitante después de confirmar la transacción.
            if self.notificaciones is not None:
                transaction.on_commit(
                    lambda: self.notificaciones.enviar(
                        prestamo.solicitante_id,
                        TipoNotificacion.ITEM_DANIADO,
                        f"El ítem asociado al préstamo {prestamo.id} "
                        "ha sido registrado como dañado y enviado a mantenimiento."
                    )
                )
        else:
            self.catalogo.marcar_disponible(prestamo.item_id)

        # Finalizar la reserva asociada al préstamo.
        self.reservas.liberar(prestamo.reserva_id)

        # Registrar auditoría.
        if self.auditoria is not None:
            self.auditoria.registrar(
                actor_id=dto.encargado_id,
                accion="DEVOLUCION_PRESTAMO",
                entidad="Prestamo",
                entidad_id=prestamo.id,
                motivo=(
                    f"Devolución registrada. "
                    f"Ítem dañado: {dto.item_daniado}. "
                    f"Garantía devuelta: {dto.garantia_devuelta}."
                )
            )

        return PrestamoDTO.desde_modelo(prestamo)

    def listar_vencidos(self):
        return [PrestamoDTO.desde_modelo(p) for p in self.repositorio.vencidos()]

    def historial_de(self, solicitante_id):
        return [
            PrestamoDTO.desde_modelo(p)
            for p in self.repositorio.historial_de(solicitante_id)
        ]
    def buscar_vencidos(self, solicitante_id=None, item_id=None):
        prestamos = self.repositorio.buscar_vencidos(
            solicitante_id=solicitante_id,
            item_id=item_id
        )

        return [
            PrestamoDTO.desde_modelo(p)
            for p in prestamos
        ]

    @transaction.atomic
    def cerrar_por_perdida(self, prestamo_id):
        prestamo = self._prestamo(prestamo_id)
        if self.reservas is None:
            raise ValidationError(
                "Falta el servicio de Reservas para cerrar el préstamo por pérdida."
            )
        prestamo.cerrar_por_perdida()

        self.reservas.finalizar_por_perdida(prestamo.reserva_id)

        return prestamo
    def entregados_hoy(self):
        return self.repositorio.entregados_hoy()

    def abiertos(self):
        return [
            PrestamoDTO.desde_modelo(p)
            for p in self.repositorio.abiertos()
        ]

class AprobarYEntregarPrestamo:
    def __init__(self, prestamo_servicio):
        self.servicio = prestamo_servicio
    def ejecutar(self, dto):
        return self.servicio.registrar_entrega(dto)

class RegistrarDevolucion:
    def __init__(self, prestamo_servicio):
        self.servicio = prestamo_servicio
    def ejecutar(self, dto):
        return self.servicio.registrar_devolucion(dto)

class RenovarPrestamo:
    def __init__(self, prestamo_servicio):
        self.servicio = prestamo_servicio
    def ejecutar(self, prestamo_id, nueva_hora_fin):
        return self.servicio.renovar(prestamo_id, nueva_hora_fin)
