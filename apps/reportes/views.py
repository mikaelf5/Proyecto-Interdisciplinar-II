from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import ReporteForm
from .models import Reporte


class ReporteListView(LoginRequiredMixin, ListView):
    model = Reporte
    template_name = "reportes/reporte_list.html"
    context_object_name = "reportes"
    paginate_by = 15


class ReporteCreateView(LoginRequiredMixin, CreateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"
    success_url = reverse_lazy("reportes:lista")

    def form_valid(self, form):
        form.instance.generado_por_id = self.request.user.id
        messages.success(self.request, "Reporte generado correctamente.")
        return super().form_valid(form)


class ReporteUpdateView(LoginRequiredMixin, UpdateView):
    model = Reporte
    form_class = ReporteForm
    template_name = "reportes/reporte_form.html"
    success_url = reverse_lazy("reportes:lista")


class ReporteDeleteView(LoginRequiredMixin, DeleteView):
    model = Reporte
    template_name = "reportes/reporte_confirm_delete.html"
    success_url = reverse_lazy("reportes:lista")


def exportar_reporte(request, pk, formato):
    """
    Llama al stub Reporte.exportar(). Mientras la lógica de negocio real
    (openpyxl/reportlab) no esté implementada, muestra un aviso en vez
    de fallar con un error sin manejar.
    """
    reporte = get_object_or_404(Reporte, pk=pk)
    formato = formato.upper()  # la URL trae 'excel'/'pdf'; FormatoExport usa 'EXCEL'/'PDF'
    try:
        reporte.exportar(formato)
    except ValueError:
        messages.error(request, f"Formato no soportado: {formato}.")
    except NotImplementedError:
        messages.info(
            request,
            f"La exportación a {formato} todavía no está implementada "
            "(queda pendiente para la fase de lógica de negocio).",
        )
    return redirect("reportes:lista")