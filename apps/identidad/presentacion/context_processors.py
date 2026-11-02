"""Menú según el rol (RF-B5): da a TODAS las plantillas qué opciones ver.

Ojo: ocultar un enlace NO es seguridad. Cada vista igual se protege con
RolRequeridoMixin; esto solo evita mostrar opciones que darían 403.
"""
from apps.common.choices import RolSistema


def menu_por_rol(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"menu": {}}

    def tiene(rol):
        return usuario.is_superuser or usuario.tiene_rol(rol)

    return {"menu": {
        "es_solicitante": tiene(RolSistema.SOLICITANTE),
        "es_encargado": tiene(RolSistema.ENCARGADO),
        "es_supervisor": tiene(RolSistema.SUPERVISOR),
        "es_admin": tiene(RolSistema.ADMINISTRADOR),
        "puede_panel": usuario.is_staff,
    }}
