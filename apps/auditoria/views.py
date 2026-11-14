from django.views.generic import ListView

from apps.common.choices import RolSistema
from apps.identidad.presentacion.permisos import RolRequeridoMixin

from .dominio.models import TipoAccion
from .fabrica import auditoria_servicio

FILTROS = ("accion", "entidad", "actor", "q", "desde", "hasta")


class _SoloAdministrador(RolRequeridoMixin):
    """Solo el personal autorizado puede entrar (RF-B5, RNF-1)."""

    roles_permitidos = [RolSistema.ADMINISTRADOR]


class RegistroAuditoriaListView(_SoloAdministrador, ListView):
    """Solo lectura. Filtros: acción, entidad, actor (ID), texto del motivo y rango de fechas.

    La vista no consulta la base de datos: pide todo al servicio de Auditoría.
    """

    template_name = "auditoria/registro_list.html"
    context_object_name = "registros"
    paginate_by = 25

    def get_queryset(self):
        filtros = {campo: self.request.GET.get(campo, "").strip() for campo in FILTROS}
        return auditoria_servicio().buscar(filtros)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        servicio = auditoria_servicio()
        registros = list(ctx["registros"])
        nombres = servicio.nombres_de_actores({r.actor_id for r in registros})
        for r in registros:
            r.actor_nombre = nombres.get(r.actor_id, "")
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            registros=registros,
            querystring=params.urlencode(),
            acciones=TipoAccion.choices,
            entidades=servicio.entidades(),
        )
        return ctx
