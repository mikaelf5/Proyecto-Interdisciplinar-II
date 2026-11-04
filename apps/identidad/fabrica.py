"""Composición: arma el servicio de aplicación con sus implementaciones concretas.

Uso desde otro contexto:

    from apps.identidad.fabrica import cuenta_servicio

    resultado = cuenta_servicio().consultar_habilitacion(solicitud.solicitante_id)  # Circulación
    tipo = cuenta_servicio().tipo_usuario_de(cuenta_id)                            # Políticas/Reservas
    cuenta_servicio().actualizar_etiqueta(cuenta_id)  # Sanciones, después de aplicar/levantar
"""
from django.conf import settings
from django.db import transaction

from apps.auditoria.fabrica import auditoria_servicio

from .aplicacion.registro import RegistroServicioAplicacion
from .aplicacion.servicios import UMBRAL_FRECUENTE_POR_DEFECTO, CuentaServicioAplicacion
from .infraestructura.adaptadores import HistorialPrestamosAdaptador, SancionesAdaptador
from .infraestructura.correo_registro import CorreoRegistroDjango
from .infraestructura.django_password_hasher import DjangoPasswordHasher
from .infraestructura.repositorio_django import (
    CuentaRepositorioImpl,
    PerfilSolicitanteRepositorioImpl,
    SolicitudRegistroRepositorioImpl,
)


def cuenta_servicio():
    return CuentaServicioAplicacion(
        CuentaRepositorioImpl(),
        PerfilSolicitanteRepositorioImpl(),
        DjangoPasswordHasher(),
        auditoria_servicio(),
        sanciones=SancionesAdaptador(),
        historial=HistorialPrestamosAdaptador(),
        umbral_frecuente=getattr(
            settings, "IDENTIDAD_PRESTAMOS_PARA_FRECUENTE", UMBRAL_FRECUENTE_POR_DEFECTO
        ),
        transaccion=transaction.atomic,
        solicitudes=SolicitudRegistroRepositorioImpl(),
    )


def registro_servicio(url_login=""):
    """`url_login` (absoluta) va en el correo de aprobación; la arma la vista con el request."""
    return RegistroServicioAplicacion(
        SolicitudRegistroRepositorioImpl(),
        CuentaRepositorioImpl(),
        PerfilSolicitanteRepositorioImpl(),
        DjangoPasswordHasher(),
        correo=CorreoRegistroDjango(url_login),
        auditoria=auditoria_servicio(),
        transaccion=transaction.atomic,
    )
