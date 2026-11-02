"""Permisos del panel /admin/ para el rol Administrador.

Las Políticas (módulo de Marving) todavía se configuran en el panel de
Django. Un Administrador que NO es superusuario entra al panel (is_staff),
pero Django además le pide permisos por modelo. Este grupo se los da.

Es infraestructura (tablas auth_group / auth_permission de Django): el
dominio solo sabe "tiene o no tiene el rol".
"""
from django.contrib.auth.models import Group, Permission

from apps.common.choices import RolSistema

NOMBRE_GRUPO = "Administradores del sistema"
APPS_DEL_ADMINISTRADOR = ("politicas",)


def grupo_administradores():
    grupo, creado = Group.objects.get_or_create(name=NOMBRE_GRUPO)
    if creado or not grupo.permissions.exists():
        grupo.permissions.set(
            Permission.objects.filter(content_type__app_label__in=APPS_DEL_ADMINISTRADOR)
        )
    return grupo


def sincronizar_grupo_administradores(cuenta):
    grupo = grupo_administradores()
    if cuenta.tiene_rol(RolSistema.ADMINISTRADOR):
        cuenta.groups.add(grupo)
    else:
        cuenta.groups.remove(grupo)
