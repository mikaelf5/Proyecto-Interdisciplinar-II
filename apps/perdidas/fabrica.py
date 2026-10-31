from apps.auditoria.fabrica import auditoria_servicio

from .aplicacion.servicios import CasoPerdidaServicioAplicacion
from .infraestructura.repositorio_django import CasoPerdidaRepositorioImpl


def caso_perdida_servicio():
    # Imports dentro de la función: así no se cargan Circulación ni Catálogo
    # cuando solo se necesita, por ejemplo, listar casos.
    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    from apps.circulacion.fabrica import prestamo_servicio

    return CasoPerdidaServicioAplicacion(
        CasoPerdidaRepositorioImpl(),
        auditoria_servicio(),
        circulacion=prestamo_servicio(),
        catalogo=CatalogoServicioAplicacion(),
    )
