from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from .models import RegistroAuditoria, TipoAccion


class RegistroAuditoriaListView(LoginRequiredMixin, ListView):
    """Solo lectura. Filtros: acción, entidad, actor (ID) y rango de fechas."""

    model = RegistroAuditoria
    template_name = "auditoria/registro_list.html"
    context_object_name = "registros"
    paginate_by = 25

    def get_queryset(self):
        get = self.request.GET
        qs = RegistroAuditoria.objects.all().order_by("-fecha_hora")
        if get.get("accion"):
            qs = qs.filter(accion=get["accion"])
        if get.get("entidad"):
            qs = qs.filter(entidad=get["entidad"])
        actor = get.get("actor", "").strip()
        if actor:
            qs = qs.filter(actor_id__icontains=actor)
        desde, hasta = parse_date(get.get("desde", "")), parse_date(get.get("hasta", ""))
        if desde:
            qs = qs.filter(fecha_hora__date__gte=desde)
        if hasta:
            qs = qs.filter(fecha_hora__date__lte=hasta)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            querystring=params.urlencode(),
            acciones=TipoAccion.choices,
            entidades=RegistroAuditoria.objects.order_by("entidad")
            .values_list("entidad", flat=True).distinct(),
        )
        return ctx
