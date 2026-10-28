"""Control de acceso por rol para las vistas (RF-B5, RNF-1).

Uso en cualquier módulo:

    from apps.identidad.presentacion.permisos import RolRequeridoMixin
    from apps.common.choices import RolSistema

    class SancionCreateView(RolRequeridoMixin, CreateView):
        roles_permitidos = [RolSistema.ENCARGADO, RolSistema.ADMINISTRADOR]
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RolRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Exige sesión iniciada y al menos uno de `roles_permitidos`.

    El superusuario siempre pasa. Si no tiene el rol, responde 403.
    """
    roles_permitidos = ()

    def test_func(self):
        usuario = self.request.user
        if usuario.is_superuser:
            return True
        return usuario.tiene_algun_rol(*self.roles_permitidos)
