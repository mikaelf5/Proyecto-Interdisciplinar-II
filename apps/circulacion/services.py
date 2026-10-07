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
    Determina el flujo de aprobación de una solicitud.

    Considera si el recurso requiere aprobación normal
    o aprobación adicional de un supervisor.
    """
    pass