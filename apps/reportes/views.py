from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.auditoria.utils import actor_id_de

from .dominio.datos import ReporteNoDisponible
from .dominio.exportador import FORMATOS
from .fabrica import reporte_servicio
from .forms import ReporteForm
from .models import Reporte


class _ObtenerPorServicio:
    def get_object(self, queryset=None):
        reporte = reporte_servicio().obtener(self.kwargs["pk"])
        if reporte is None:
            raise Http404("Reporte no encontrado")
        return reporte


class ReporteListView(LoginRequiredMixin, ListView):
    model = Reporte
    template_name = "reportes/reporte_list.html"
    context_object_name = "reportes"
    paginate_by = 15

    def get_queryset(self):
        return reporte_servicio().listar()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        servicio = reporte_servicio()
        for r in ctx["reportes"]:
            r.disponible = servicio.esta_disponible(r.tipo)
        return ctx


class ReporteCreateView(LoginRequiredMixin, CreateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"

    def form_valid(self, form):
        self.object = reporte_servicio().crear(
            form.save(commit=False), actor_id_de(self.request)
        )
        messages.success(self.request, "Reporte generado.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("reportes:detalle", args=[self.object.pk])


class ReporteUpdateView(LoginRequiredMixin, _ObtenerPorServicio, UpdateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"

    def form_valid(self, form):
        self.object = reporte_servicio().actualizar(form.save(commit=False))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("reportes:detalle", args=[self.object.pk])


class ReporteDetailView(LoginRequiredMixin, _ObtenerPorServicio, DetailView):
    model = Reporte
    template_name = "reportes/reporte_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx["datos"] = reporte_servicio().generar_datos(self.object)
        except ReporteNoDisponible as error:
            ctx["no_disponible"] = str(error)
        return ctx


class ReporteDeleteView(LoginRequiredMixin, _ObtenerPorServicio, DeleteView):
    model = Reporte
    template_name = "reportes/reporte_confirm_delete.html"
    success_url = reverse_lazy("reportes:lista")

    def form_valid(self, form):
        reporte_servicio().eliminar(self.object)
        return HttpResponseRedirect(self.get_success_url())


def exportar_reporte(request, pk, formato):
    """Descarga el reporte en Excel o PDF."""
    if not request.user.is_authenticated:
        return redirect(f"/admin/login/?next={request.path}")
    if formato not in FORMATOS:
        raise Http404("Formato no soportado")
    servicio = reporte_servicio()
    reporte = servicio.obtener(pk)
    if reporte is None:
        raise Http404("Reporte no encontrado")
    try:
        contenido, content_type, nombre = servicio.exportar(reporte, formato)
    except ReporteNoDisponible as error:
        messages.info(request, str(error))
        return redirect("reportes:lista")
    respuesta = HttpResponse(contenido, content_type=content_type)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta