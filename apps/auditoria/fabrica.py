from .aplicacion.servicios import AuditoriaServicioAplicacion
from .infraestructura.repositorio_django import RegistroAuditoriaRepositorioImpl


def auditoria_servicio():
    return AuditoriaServicioAplicacion(RegistroAuditoriaRepositorioImpl())