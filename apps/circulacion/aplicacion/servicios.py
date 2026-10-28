"""Casos de uso de Circulación. Las dependencias externas se inyectan."""
from abc import ABC, abstractmethod
from datetime import datetime, time
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.common.choices import EstadoSolicitud, EstadoPrestamo, TipoGarantia
from apps.circulacion.dominio.models import Solicitud, Prestamo
from apps.circulacion.aplicacion.dtos import PrestamoDTO

class ISolicitudServicio(ABC):
    @abstractmethod
    def solicitar(self, dto): ...
    @abstractmethod
    def aprobar(self, id, encargado_id): ...
    @abstractmethod
    def aprobar_como_supervisor(self, id, supervisor_id): ...
    @abstractmethod
    def rechazar(self, id, encargado_id, motivo): ...
    @abstractmethod
    def cancelar(self, id): ...

class SolicitudServicioAplicacion(ISolicitudServicio):
    def __init__(self, solicitud_repositorio, elegibilidad=None, aprobacion=None):
        self.repositorio = solicitud_repositorio
        self.elegibilidad = elegibilidad
        self.aprobacion = aprobacion

    def _obtener(self, id):
        solicitud = self.repositorio.buscar_por_id(id)
        if solicitud is None:
            raise ValidationError("No existe la solicitud.")
        return solicitud

    def solicitar(self, dto):
        solicitud = Solicitud(item_id=dto.item_id, categoria_id=dto.categoria_id,
                             solicitante_id=dto.solicitante_id, fecha_inicio=dto.fecha_inicio,
                             fecha_fin=dto.fecha_fin, finalidad=dto.finalidad)
        solicitud.full_clean()
        return self.repositorio.guardar(solicitud)

    def aprobar(self, id, encargado_id):
        with transaction.atomic():
            solicitud = self._obtener(id)
            if self.aprobacion is not None:
                estado = self.aprobacion.determinar_flujo(solicitud)
                if estado == EstadoSolicitud.EN_ESPERA_SUPERVISOR:
                    return solicitud
            solicitud.aprobar(encargado_id)
            return solicitud

    def aprobar_como_supervisor(self, id, supervisor_id):
        with transaction.atomic():
            solicitud = self._obtener(id)
            solicitud.aprobar_como_supervisor(supervisor_id)
            return solicitud

    def rechazar(self, id, encargado_id, motivo):
        with transaction.atomic():
            solicitud = self._obtener(id)
            solicitud.rechazar(motivo, encargado_id)
            return solicitud

    def cancelar(self, id):
        with transaction.atomic():
            solicitud = self._obtener(id)
            solicitud.cancelar()
            return solicitud

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
    def cerrar_por_perdida(self, prestamo_id): ...

class PrestamoServicioAplicacion(IPrestamoServicio):
    def __init__(self, prestamo_repositorio, solicitud_repositorio=None,
                 elegibilidad=None, catalogo=None, politica_servicio=None,
                 auditoria=None, condicion_servicio=None, resolver_politica=None):
        self.repositorio = prestamo_repositorio
        self.solicitudes = solicitud_repositorio
        self.elegibilidad = elegibilidad
        self.catalogo = catalogo
        self.politicas = politica_servicio
        self.auditoria = auditoria
        self.condiciones = condicion_servicio
        self.resolver_politica = resolver_politica

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

    def _prestamo(self, id):
        p = self.repositorio.buscar_por_id(id)
        if p is None:
            raise ValidationError("No existe el préstamo.")
        return p

    def _politica(self, prestamo):
        if self.resolver_politica is None:
            raise ValidationError("Falta integrar la resolución de política por usuario y categoría.")
        politica = self.resolver_politica(prestamo.solicitante_id, prestamo.item_id)
        if politica is None:
            raise ValidationError("No existe una política aplicable.")
        return politica

    def registrar_entrega(self, dto):
        """Entrega atómica con servicios externos inyectados y validados.

        elegibilidad.evaluar(solicitante_id, item_id) -> bool o resultado.habilitado
        catalogo.esta_disponible(item_id), catalogo.marcar_prestado(item_id)
        catalogo.registrar_condicion(NuevaCondicionDTO) y auditoria.registrar(...)
        resolver_politica(solicitante_id, item_id) -> PoliticaPrestamo
        """
        if any(dep is None for dep in (self.solicitudes, self.elegibilidad,
                                         self.catalogo, self.auditoria,
                                         self.resolver_politica)):
            raise ValidationError("Faltan dependencias para registrar la entrega.")
        if not dto.terminos_aceptados:
            raise ValidationError("Debe aceptar los términos del préstamo.")
        if dto.garantia_tipo not in TipoGarantia.values:
            raise ValidationError("Tipo de garantía no válido.")
        if dto.garantia_tipo == TipoGarantia.OTRO and not dto.garantia_detalle.strip():
            raise ValidationError("Debe describir la garantía de tipo OTRO.")
        with transaction.atomic():
            solicitud = self.solicitudes.buscar_por_id(dto.solicitud_id)
            if solicitud is None or solicitud.estado != EstadoSolicitud.APROBADA:
                raise ValidationError("La solicitud debe estar aprobada.")
            if solicitud.item_id is None:
                raise ValidationError("Debe asignarse un ítem concreto antes de la entrega.")
            if self.repositorio.existe_abierto_para_item(solicitud.item_id):
                raise ValidationError("El ítem ya tiene un préstamo abierto.")
            aptitud = self.elegibilidad.evaluar(solicitud.solicitante_id, solicitud.item_id)
            es_apto = (aptitud if isinstance(aptitud, bool)
                       else getattr(aptitud, "apto", getattr(aptitud, "habilitado", False)))
            if not es_apto:
                motivos = getattr(aptitud, "motivos", ())
                detalle = "; ".join(str(m) for m in motivos) if motivos else ""
                raise ValidationError(
                    "El solicitante no es elegible." + (" " + detalle if detalle else "")
                )
            if not self.catalogo.esta_disponible(solicitud.item_id):
                raise ValidationError("El ítem no está disponible.")
            politica = self.resolver_politica(solicitud.solicitante_id, solicitud.item_id)
            if politica is None:
                raise ValidationError("No existe política aplicable.")
            ahora = timezone.now()
            limite = politica.calcular_vencimiento(ahora)
            # Solicitud.fecha_fin es DateField: fin de ese día, no una hora solicitada.
            fin_dia = timezone.make_aware(datetime.combine(solicitud.fecha_fin, time.max))
            vencimiento = dto.fecha_vencimiento or min(fin_dia, limite)
            if timezone.is_naive(vencimiento):
                raise ValidationError("El vencimiento debe incluir zona horaria.")
            if vencimiento <= ahora or vencimiento > limite or vencimiento > fin_dia:
                raise ValidationError("La fecha de devolución no cumple el plazo solicitado y la política.")
            prestamo = Prestamo(item_id=solicitud.item_id, solicitante_id=solicitud.solicitante_id,
                solicitud_id=solicitud.id, encargado_entrega_id=dto.encargado_id,
                garantia_tipo=dto.garantia_tipo, garantia_detalle=dto.garantia_detalle,
                terminos_aceptados=True, fecha_entrega=ahora, fecha_vencimiento=vencimiento)
            prestamo.full_clean()
            self.repositorio.guardar(prestamo)
            self.catalogo.marcar_prestado(prestamo.item_id)
            self._registrar_condicion(
                prestamo.item_id, prestamo.id, dto.encargado_id,
                "ENTREGA", ahora, "Condición física al entregar"
            )
            self.auditoria.registrar(dto.encargado_id, "ENTREGA", "Prestamo", prestamo.id)
            return PrestamoDTO.desde_modelo(prestamo)

    def renovar(self, id):
        with transaction.atomic():
            prestamo = self._prestamo(id)
            politica = self._politica(prestamo)
            prestamo.renovar(politica)
            return PrestamoDTO.desde_modelo(prestamo)

    def registrar_devolucion(self, dto):
        if self.catalogo is None:
            raise ValidationError("Se requiere Catálogo y registro de condición física para devolver.")
        if not dto.descripcion_condicion.strip():
            raise ValidationError("Debe registrar la condición física del ítem.")
        with transaction.atomic():
            prestamo = self._prestamo(dto.prestamo_id)
            if prestamo.estado not in (EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO):
                raise ValidationError("El préstamo no está abierto.")
            ahora = timezone.now()
            self._registrar_condicion(
                prestamo.item_id, prestamo.id, dto.encargado_id,
                "DEVOLUCION", ahora, dto.descripcion_condicion, dto.foto
            )
            prestamo.registrar_devolucion(dto.descripcion_condicion, dto.encargado_id, ahora)
            # No cambiar automáticamente el estado de Catálogo: requiere inspección
            # y un contrato explícito para habilitar nuevamente el ítem.
            if self.auditoria is not None:
                self.auditoria.registrar(dto.encargado_id, "DEVOLUCION", "Prestamo", prestamo.id)
            return PrestamoDTO.desde_modelo(prestamo)

    def listar_vencidos(self):
        return [PrestamoDTO.desde_modelo(p) for p in self.repositorio.vencidos()]

    def cerrar_por_perdida(self, prestamo_id):
        with transaction.atomic():
            prestamo = self._prestamo(prestamo_id)
            prestamo.cerrar_por_perdida()
            return prestamo

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
    def ejecutar(self, prestamo_id):
        return self.servicio.renovar(prestamo_id)
