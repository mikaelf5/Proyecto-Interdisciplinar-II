from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.common.choices import RolSistema
from apps.identidad.presentacion.permisos import RolRequeridoMixin
from apps.auditoria.models import TipoAccion
from apps.auditoria.utils import actor_id_de, auditar

from .forms import SancionForm
from .infraestructura import consultas
from .models import Sancion, TipoSancion
from .servicios import ESTADOS, LEVANTADA, VIGENTE, con_estado


class _SoloPersonal(RolRequeridoMixin):
    """Solo el personal autorizado puede entrar (RF-B5, RNF-1)."""

    roles_permitidos = [RolSistema.ENCARGADO, RolSistema.ADMINISTRADOR]



class SancionListView(_SoloPersonal, ListView):
    """Lista con filtros por tipo, estado y búsqueda (nombre, DNI o CUI del solicitante, o motivo)."""

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
            qs = qs.filter(Q(solicitante_id__in=consultas.ids_que_coinciden(q)) | Q(motivo__icontains=q))
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
        _con_nombres(ctx["sanciones"])
        return ctx


class SancionHistorialView(_SoloPersonal, ListView):
    """Todas las sanciones de un solicitante (RF-G1)."""

    template_name = "sanciones/sancion_historial.html"
    context_object_name = "sanciones"

    def get_queryset(self):
        qs = Sancion.objects.filter(solicitante_id=self.kwargs["solicitante_id"])
        return con_estado(qs.order_by("-fecha_inicio", "-creado_en"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sanciones = ctx["sanciones"]
        solicitante_id = self.kwargs["solicitante_id"]
        nombre, dni = consultas.personas({solicitante_id}).get(solicitante_id, ("", ""))
        ctx.update(
            solicitante_id=solicitante_id,
            solicitante_nombre=nombre,
            solicitante_dni=dni,
            total=len(sanciones),
            vigentes=sum(1 for s in sanciones if s.estado == VIGENTE),
        )
        return ctx


class SancionCreateView(_SoloPersonal, CreateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "actor_id": actor_id_de(self.request)}

    

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


class SancionUpdateView(_SoloPersonal, UpdateView):
    model = Sancion
    form_class = SancionForm
    template_name = "sanciones/sancion_form.html"
    success_url = reverse_lazy("sanciones:lista")

    def get_form_kwargs(self):
            return {**super().get_form_kwargs(), "actor_id": actor_id_de(self.request)}

    def form_valid(self, form):
        response = super().form_valid(form)
        auditar(
            self.request, TipoAccion.SANCION, "Sancion", self.object.pk,
            f"Sanción modificada: {self.object.motivo}",
        )
        messages.success(self.request, "Sanción actualizada.")
        return response


class SancionLevantarView(_SoloPersonal, View):
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


class SancionDeleteView(_SoloPersonal, DeleteView):
    model = Sancion
    template_name = "sanciones/sancion_confirm_delete.html"
    success_url = reverse_lazy("sanciones:lista")

    def form_valid(self, form):
        s = self.object
        nombre = consultas.personas({s.solicitante_id}).get(s.solicitante_id, (str(s.solicitante_id),))[0]
        pk, descripcion = s.pk, f"{s.get_tipo_display()} de {nombre}"
        response = super().form_valid(form)
        auditar(self.request, TipoAccion.SANCION, "Sancion", pk,
                f"Sanción eliminada: {descripcion}")
        messages.success(self.request, "Sanción eliminada.")
        return response


def _con_nombres(sanciones):
    """Agrega .solicitante_nombre y .solicitante_dni (solo en memoria) para mostrarlos en la lista."""
    datos = consultas.personas({s.solicitante_id for s in sanciones})
    for s in sanciones:
        s.solicitante_nombre, s.solicitante_dni = datos.get(s.solicitante_id, ("", ""))
