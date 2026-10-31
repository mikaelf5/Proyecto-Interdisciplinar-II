from .aplicacion.servicios import SancionServicioAplicacion
from .infraestructura.repositorio_django import SancionRepositorioImpl


def sancion_servicio():
    return SancionServicioAplicacion(SancionRepositorioImpl())


def revisor_vencimientos():
    """Arma el revisor de vencimientos con Circulación, Notificaciones, Catálogo y Auditoría."""
    from apps.auditoria.fabrica import auditoria_servicio
    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion

    from .aplicacion.vencimientos import RevisorDeVencimientos
    from .infraestructura.prestamos_circulacion import PrestamosDeCirculacion

    return RevisorDeVencimientos(
        PrestamosDeCirculacion(),
        NotificacionServicioAplicacion(),
        CatalogoServicioAplicacion(),
        auditoria_servicio(),
    )
