from django.core.exceptions import ValidationError
from apps.common.choices import EstadoSolicitud

class AprobarYEntregarPrestamo:
    """
    Coordina la aprobación de una solicitud y la entrega del ítem.

    Debe validar elegibilidad del solicitante, disponibilidad del ítem,
    políticas de préstamo y aprobación de supervisor cuando corresponda.
    """
    pass


class RegistrarDevolucion:
    """
    Coordina la devolución de un préstamo.

    Debe registrar la fecha de devolución, condición física del ítem
    y determinar si corresponde cerrar normalmente o generar incidencias.
    """
    pass


class RenovarPrestamo:
    """
    Coordina la renovación de un préstamo.

    Debe comprobar las políticas aplicables y el número máximo
    de renovaciones permitidas.
    """
    pass


class ServicioDeElegibilidad:
    """
    Determina si un solicitante está habilitado para obtener un préstamo.

    Puede considerar su estado institucional, sanciones activas
    y límites de préstamos simultáneos.
    """
    pass


class ServicioDeAprobacion:
    """
    Determina si una solicitud necesita aprobación de supervisor.
    """

    def __init__(self, catalogo):
        self.catalogo = catalogo

    def requiere_supervisor(self, solicitud):
        return self.catalogo.es_especial(
            item_id=solicitud.item_id,
            categoria_id=solicitud.categoria_id,
        )
    def determinar_flujo(self, solicitud):
        if solicitud.estado != EstadoSolicitud.PENDIENTE:
            raise ValidationError(
                "Solo se puede determinar el flujo de una solicitud pendiente."
            )

        if self.requiere_supervisor(solicitud):
            solicitud.validar_transicion(
                EstadoSolicitud.EN_ESPERA_SUPERVISOR
            )
            solicitud.estado = EstadoSolicitud.EN_ESPERA_SUPERVISOR
            solicitud.save()

        return solicitud.estado