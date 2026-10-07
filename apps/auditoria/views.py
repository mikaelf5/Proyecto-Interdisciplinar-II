from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from .models import RegistroAuditoria


class RegistroAuditoriaListView(LoginRequiredMixin, ListView):
    """
    Solo lectura: la auditoría se genera automáticamente desde los
    servicios del dominio (RegistroAuditoria.registrar(...)), nunca
    se crea ni edita a mano desde la interfaz.
    """

    model = RegistroAuditoria
    template_name = "auditoria/registro_list.html"
    context_object_name = "registros"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        accion = self.request.GET.get("accion")
        if accion:
            qs = qs.filter(accion=accion)
        return qs