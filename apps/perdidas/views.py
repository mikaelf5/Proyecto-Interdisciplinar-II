from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.auditoria.utils import actor_id_de

from .fabrica import caso_perdida_servicio
from .forms import CasoPerdidaForm
from .models import CasoPerdida


class _ObtenerPorServicio:
    """get_object() pasa por el servicio, no por el ORM."""

    def get_object(self, queryset=None):
        caso = caso_perdida_servicio().obtener(self.kwargs["pk"])
        if caso is None:
            raise Http404("Caso no encontrado")
        return caso


class CasoPerdidaListView(LoginRequiredMixin, ListView):
    model = CasoPerdida
    template_name = "perdidas/caso_list.html"
    context_object_name = "casos"
    paginate_by = 15

    def get_queryset(self):
        get = self.request.GET
        return caso_perdida_servicio().listar(get.get("estado", ""), get.get("q", ""))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            querystring=params.urlencode(),
            abiertos=caso_perdida_servicio().contar_abiertos(),
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
        self.object = caso_perdida_servicio().registrar(
            form.save(commit=False), actor_id_de(self.request)
        )
        messages.success(
            self.request,
            "Caso de pérdida registrado. Puedes aplicar una sanción desde la lista.",
        )
        return HttpResponseRedirect(self.get_success_url())


class CasoPerdidaUpdateView(LoginRequiredMixin, _ObtenerPorServicio, UpdateView):
    model = CasoPerdida
    form_class = CasoPerdidaForm
    template_name = "perdidas/caso_form.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        self.object = caso_perdida_servicio().actualizar(form.save(commit=False))
        messages.success(self.request, "Caso de pérdida actualizado.")
        return HttpResponseRedirect(self.get_success_url())


class CasoPerdidaCerrarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        servicio = caso_perdida_servicio()
        caso = servicio.obtener(pk)
        if caso is None:
            raise Http404("Caso no encontrado")
        if servicio.cerrar(caso, actor_id_de(request)):
            messages.success(request, "Caso cerrado.")
        else:
            messages.info(request, "Ese caso ya estaba cerrado.")
        return redirect("perdidas:lista")


class CasoPerdidaDeleteView(LoginRequiredMixin, _ObtenerPorServicio, DeleteView):
    model = CasoPerdida
    template_name = "perdidas/caso_confirm_delete.html"
    success_url = reverse_lazy("perdidas:lista")

    def form_valid(self, form):
        caso_perdida_servicio().eliminar(self.object, actor_id_de(self.request))
        messages.success(self.request, "Caso eliminado.")
        return HttpResponseRedirect(self.get_success_url())