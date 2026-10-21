"""Composición: arma el servicio de aplicación con sus implementaciones concretas.

Uso desde otro contexto (ej. Circulación):

    from apps.identidad.fabrica import cuenta_servicio

    resultado = cuenta_servicio().consultar_habilitacion(solicitud.solicitante_id)
    if not resultado:
        solicitud.rechazar(resultado.mensaje)
"""
from apps.auditoria.fabrica import auditoria_servicio

from .aplicacion.servicios import CuentaServicioAplicacion
from .infraestructura.django_password_hasher import DjangoPasswordHasher
from .infraestructura.repositorio_django import (
    CuentaRepositorioImpl,
    PerfilSolicitanteRepositorioImpl,
)


def cuenta_servicio():
    return CuentaServicioAplicacion(
        CuentaRepositorioImpl(),
        PerfilSolicitanteRepositorioImpl(),
        DjangoPasswordHasher(),
        auditoria_servicio(),
    )
