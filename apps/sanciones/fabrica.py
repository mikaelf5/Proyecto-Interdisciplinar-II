from .aplicacion.servicios import SancionServicioAplicacion
from .infraestructura.repositorio_django import SancionRepositorioImpl


def sancion_servicio():
    return SancionServicioAplicacion(SancionRepositorioImpl())