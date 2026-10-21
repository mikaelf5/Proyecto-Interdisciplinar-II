from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.auditoria.utils import actor_id_de

from .exportadores import FORMATOS, exportar
from .forms import ReporteForm
from .models import Reporte
from .servicios import ReporteNoDisponible, esta_disponible, generar_datos


class ReporteListView(LoginRequiredMixin, ListView):
    model = Reporte
    template_name = "reportes/reporte_list.html"
    context_object_name = "reportes"
    paginate_by = 15

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for r in ctx["reportes"]:
            r.disponible = esta_disponible(r.tipo)
        return ctx


class ReporteCreateView(LoginRequiredMixin, CreateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"

    def form_valid(self, form):
        form.instance.generado_por_id = actor_id_de(self.request)
        messages.success(self.request, "Reporte generado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("reportes:detalle", args=[self.object.pk])


class ReporteUpdateView(LoginRequiredMixin, UpdateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"

    def get_success_url(self):
        return reverse("reportes:detalle", args=[self.object.pk])


class ReporteDetailView(LoginRequiredMixin, DetailView):
    """Muestra el reporte calculado con los datos actuales del periodo."""

    model = Reporte
    template_name = "reportes/reporte_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["datos"] = generar_datos(self.object)
        except ReporteNoDisponible as error:
            ctx["no_disponible"] = str(error)
        return ctx


class ReporteDeleteView(LoginRequiredMixin, DeleteView):
    model = Reporte
    template_name = "reportes/reporte_confirm_delete.html"
    success_url = reverse_lazy("reportes:lista")


def exportar_reporte(request, pk, formato):
    """Descarga el reporte en Excel o PDF."""
    if not request.user.is_authenticated:
        return redirect(f"/admin/login/?next={request.path}")
    if formato not in FORMATOS:
        raise Http404("Formato no soportado")
    reporte = get_object_or_404(Reporte, pk=pk)
    try:
        contenido, content_type, nombre = exportar(reporte, formato)
    except ReporteNoDisponible as error:
        messages.info(request, str(error))
        return redirect("reportes:lista")
    respuesta = HttpResponse(contenido, content_type=content_type)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta
