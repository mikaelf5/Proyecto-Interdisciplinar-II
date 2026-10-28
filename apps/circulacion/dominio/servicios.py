"""Servicios de dominio de Circulación."""
from django.core.exceptions import ValidationError
from apps.common.choices import EstadoSolicitud

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

class ServicioDeElegibilidad:
    """Regla pura: combina información obtenida por los contextos externos."""
    def evaluar(self, perfil, tiene_sancion, politica, vigentes):
        if perfil is None or politica is None or tiene_sancion:
            return False
        habilitado = getattr(perfil, "habilitado", None)
        if habilitado is None:
            metodo = getattr(perfil, "esta_habilitado", None)
            if not callable(metodo):
                raise ValidationError("No se puede determinar la habilitación del perfil.")
            habilitado = metodo()
        if not habilitado:
            return False
        return len(vigentes) < politica.limite_simultaneo_global

# Alias con la operación declarada en el diagrama; mantiene M4.
def _decidir(self, solicitud, es_especial):
    if solicitud.estado != EstadoSolicitud.PENDIENTE:
        raise ValidationError("La solicitud debe estar pendiente.")
    return EstadoSolicitud.EN_ESPERA_SUPERVISOR if es_especial else EstadoSolicitud.APROBADA
ServicioDeAprobacion.decidir = _decidir
