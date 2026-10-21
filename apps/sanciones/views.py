from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.auditoria.models import TipoAccion
from apps.auditoria.utils import actor_id_de, auditar

from .forms import SancionForm
from .models import Sancion, TipoSancion
from .servicios import ESTADOS, LEVANTADA, VIGENTE, con_estado


class SancionListView(LoginRequiredMixin, ListView):
    """Lista con filtros por tipo, estado y búsqueda (solicitante o motivo)."""

    model = Sancion
    template_name = "sanciones/sancion_list.html"
    context_object_name = "sanciones"
    paginate_by = 15

    def get_queryset(self):
        get = self.request.GET
        qs = Sancion.objects.all().order_by("-fecha_inicio", "-creado_en")
        if get.get("tipo"):
            qs = qs.filter(tipo=get["tipo"])
        q = get.get("q", "").strip()
        if q:
            qs = qs.filter(Q(solicitante_id__icontains=q) | Q(motivo__icontains=q))
        sanciones = con_estado(qs)
        if get.get("estado"):
            sanciones = [s for s in sanciones if s.estado == get["estado"]]
        return sanciones

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            querystring=params.urlencode(),
            tipos=TipoSancion.choices,
            estados=ESTADOS,
            total=len(self.object_list),
        )
        return ctx


class SancionHistorialView(LoginRequiredMixin, ListView):
    """Todas las sanciones de un solicitante (RF-G1)."""

    template_name = "sanciones/sancion_historial.html"
    context_object_name = "sanciones"

    def get_queryset(self):
        qs = Sancion.objects.filter(solicitante_id=self.kwargs["solicitante_id"])
        return con_estado(qs.order_by("-fecha_inicio", "-creado_en"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sanciones = ctx["sanciones"]
        ctx.update(
            solicitante_id=self.kwargs["solicitante_id"],
            total=len(sanciones),
            vigentes=sum(1 for s in sanciones if s.estado == VIGENTE),
        )
        return ctx


class SancionCreateView(LoginRequiredMixin, CreateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def get_initial(self):
        """Permite abrir el formulario ya rellenado (ej. desde un caso de pérdida)."""
        initial = super().get_initial()
        for campo in ("solicitante_id", "prestamo_id", "motivo", "tipo"):
            valor = self.request.GET.get(campo)
            if valor:
                initial[campo] = valor
        initial.setdefault("fecha_inicio", date.today())
        return initial

    def form_valid(self, form):
        form.instance.aplicada_por_id = actor_id_de(self.request)
        form.instance.activa = True
        response = super().form_valid(form)
        s = self.object
        auditar(
            self.request, TipoAccion.SANCION, "Sancion", s.pk,
            f"{s.get_tipo_display()}: {s.motivo}",
        )
        messages.success(self.request, "Sanción registrada y anotada en la auditoría.")
        return response


class SancionUpdateView(LoginRequiredMixin, UpdateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditar(
            self.request, TipoAccion.SANCION, "Sancion", self.object.pk,
            f"Sanción modificada: {self.object.motivo}",
        )
        messages.success(self.request, "Sanción actualizada.")
        return response


class SancionLevantarView(LoginRequiredMixin, View):
    """Cierra una sanción activa; exige motivo (RF-J1) y lo audita."""

    template_name = "sanciones/sancion_levantar.html"

    def get(self, request, pk):
        sancion = get_object_or_404(Sancion, pk=pk)
        return render(request, self.template_name, {"object": sancion})

    def post(self, request, pk):
        sancion = get_object_or_404(Sancion, pk=pk)
        if not sancion.activa:
            messages.info(request, "Esa sanción ya estaba levantada.")
            return redirect("sanciones:lista")
        motivo = request.POST.get("motivo", "").strip()
        if len(motivo) < 5:
            return render(
                request, self.template_name,
                {"object": sancion, "error": "Indica el motivo (mínimo 5 caracteres).",
                 "motivo": motivo},
            )
        sancion.levantar()
        auditar(request, TipoAccion.SANCION, "Sancion", sancion.pk,
                f"Sanción levantada: {motivo}")
        messages.success(request, "Sanción levantada.")
        return redirect("sanciones:lista")


class SancionDeleteView(LoginRequiredMixin, DeleteView):
    model = Sancion
    template_name = "sanciones/sancion_confirm_delete.html"
    success_url = reverse_lazy("sanciones:lista")

    def form_valid(self, form):
        s = self.object
        pk, descripcion = s.pk, f"{s.get_tipo_display()} de {s.solicitante_id}"
        response = super().form_valid(form)
        auditar(self.request, TipoAccion.SANCION, "Sancion", pk,
                f"Sanción eliminada: {descripcion}")
        messages.success(self.request, "Sanción eliminada.")
        return response
