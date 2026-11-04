
"""Punto de composición de los servicios de Circulación."""

from apps.circulacion.aplicacion.servicios import PrestamoServicioAplicacion
from apps.circulacion.infraestructura.repositorio_django import (
    PrestamoRepositorioImpl,
)


def prestamo_servicio(**dependencias):
    """Construye el servicio de préstamos con sus dependencias."""

    # Importaciones locales para evitar dependencias circulares.
    from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    from apps.identidad.fabrica import cuenta_servicio
    from apps.politicas.fabrica import politica_servicio
    from apps.auditoria.fabrica import auditoria_servicio
    from apps.notificaciones.aplicacion.servicios import (
        NotificacionServicioAplicacion,
    )

    # Crear las dependencias compartidas.
    catalogo = dependencias.get("catalogo") or CatalogoServicioAplicacion()
    identidad = dependencias.get("identidad") or cuenta_servicio()

    politicas = (
        dependencias.get("politica_servicio")
        or politica_servicio()
    )

    reservas = dependencias.get("reservas") or ReservaServicioAplicacion(
        catalogo=catalogo,
        identidad=identidad,
        politicas=politicas,
    )

    auditoria = dependencias.get("auditoria") or auditoria_servicio()

    notificaciones = (
        dependencias.get("notificaciones")
        or NotificacionServicioAplicacion()
    )

    # Completar las dependencias del servicio.
    dependencias.update({
        "catalogo": catalogo,
        "identidad": identidad,
        "politica_servicio": politicas,
        "reservas": reservas,
        "auditoria": auditoria,
        "notificaciones": notificaciones,
        "condicion_servicio": catalogo,
    })

    return PrestamoServicioAplicacion(
        prestamo_repositorio=PrestamoRepositorioImpl(),
        **dependencias,
    )
