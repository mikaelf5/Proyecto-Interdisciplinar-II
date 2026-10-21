from apps.auditoria.fabrica import auditoria_servicio

from .aplicacion.servicios import CasoPerdidaServicioAplicacion
from .infraestructura.repositorio_django import CasoPerdidaRepositorioImpl


def caso_perdida_servicio():
    return CasoPerdidaServicioAplicacion(CasoPerdidaRepositorioImpl(), auditoria_servicio())