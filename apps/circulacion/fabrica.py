"""Punto de composición de los servicios de Circulación."""
from apps.circulacion.aplicacion.servicios import (
    SolicitudServicioAplicacion, PrestamoServicioAplicacion,
)
from apps.circulacion.infraestructura.repositorio_django import (
    SolicitudRepositorioImpl, PrestamoRepositorioImpl,
)
from apps.circulacion.dominio.servicios import ServicioDeAprobacion


def solicitud_servicio(catalogo=None):
    """Sin Catálogo se permiten casos sin aprobación, pero no aprobar."""
    aprobacion = ServicioDeAprobacion(catalogo) if catalogo is not None else None
    return SolicitudServicioAplicacion(
        solicitud_repositorio=SolicitudRepositorioImpl(),
        aprobacion=aprobacion,
    )


def prestamo_servicio(**dependencias):
    return PrestamoServicioAplicacion(
        prestamo_repositorio=PrestamoRepositorioImpl(),
        solicitud_repositorio=SolicitudRepositorioImpl(),
        **dependencias,
    )
