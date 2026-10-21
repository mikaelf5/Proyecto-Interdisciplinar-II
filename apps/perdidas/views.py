from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.auditoria.models import TipoAccion
from apps.auditoria.utils import auditar

from .forms import CasoPerdidaForm
from .models import CasoPerdida


class CasoPerdidaListView(LoginRequiredMixin, ListView):
    """Lista con filtro por estado (abierto/cerrado) y búsqueda por IDs."""

    model = CasoPerdida
    template_name = "perdidas/caso_list.html"
    context_object_name = "casos"
    paginate_by = 15

    def get_queryset(self):
        get = self.request.GET
        qs = CasoPerdida.objects.all().order_by("cerrado", "-fecha", "-creado_en")
        if get.get("estado") == "abierto":
            qs = qs.filter(cerrado=False)
        elif get.get("estado") == "cerrado":
            qs = qs.filter(cerrado=True)
        q = get.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(prestamo_id__icontains=q)
                | Q(solicitante_id__icontains=q)
                | Q(observaciones__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            querystring=params.urlencode(),
            abiertos=CasoPerdida.objects.filter(cerrado=False).count(),
        )
        return ctx


class CasoPerdidaCreateView(LoginRequiredMixin, CreateView):
    model = CasoPerdida
    form_class = CasoPerdidaForm
    template_name = "perdidas/caso_form.html"
    success_url = reverse_lazy("perdidas:lista")

    def get_initial(self):
        initial = super().get_initial()
        initial["fecha"] = date.today()
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        caso = self.object
        auditar(
            self.request, TipoAccion.ITEM_DANIADO, "CasoPerdida", caso.pk,
            f"Pérdida registrada: {caso.observaciones or 'sin observaciones'}",
        )
        messages.success(
            self.request,
            "Caso de pérdida registrado. Puedes aplicar una sanción desde la lista.",
        )
        return response


class CasoPerdidaUpdateView(LoginRequiredMixin, UpdateView):
    model = CasoPerdida
    form_class = CasoPerdidaForm
    template_name = "perdidas/caso_form.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Caso de pérdida actualizado.")
        return response


class CasoPerdidaCerrarView(LoginRequiredMixin, View):
    """Cierra el caso (y, cuando se integre Circulación, el préstamo)."""

    def post(self, request, pk):
        caso = get_object_or_404(CasoPerdida, pk=pk)
        if caso.cerrado:
            messages.info(request, "Ese caso ya estaba cerrado.")
        else:
            caso.cerrar_prestamo()
            auditar(request, TipoAccion.CAMBIO_ESTADO, "CasoPerdida", caso.pk,
                    "Caso de pérdida cerrado")
            messages.success(request, "Caso cerrado.")
        return redirect("perdidas:lista")


class CasoPerdidaDeleteView(LoginRequiredMixin, DeleteView):
    model = CasoPerdida
    template_name = "perdidas/caso_confirm_delete.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        pk, prestamo = self.object.pk, self.object.prestamo_id
        response = super().form_valid(form)
        auditar(self.request, TipoAccion.CAMBIO_ESTADO, "CasoPerdida", pk,
                f"Caso de pérdida eliminado (préstamo {prestamo})")
        messages.success(self.request, "Caso eliminado.")
        return response
