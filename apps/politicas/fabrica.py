from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl


def politica_servicio():
    return PoliticaServicioAplicacion(
        PoliticaRepositorioImpl()
    )