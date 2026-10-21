"""Vistas HTTP de Circulación: autorización en servidor y comandos por POST."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, DetailView

from apps.common.choices import EstadoSolicitud, RolSistema
from apps.circulacion.models import Solicitud
from apps.circulacion.presentacion.forms import SolicitudForm
from apps.circulacion.aplicacion.dtos import SolicitudDTO
from apps.circulacion.fabrica import solicitud_servicio


class SolicitudListView(LoginRequiredMixin, ListView):
    model = Solicitud
    template_name = "circulacion/solicitud_list.html"
    context_object_name = "solicitudes"
    paginate_by = 15


class SolicitudCreateView(LoginRequiredMixin, CreateView):
    model = Solicitud
    form_class = SolicitudForm
    template_name = "circulacion/solicitud_form.html"
    success_url = reverse_lazy("circulacion:solicitudes")

    def form_valid(self, form):
        datos = form.cleaned_data
        dto = SolicitudDTO(
            item_id=datos["item_id"],
            categoria_id=datos["categoria_id"],
            solicitante_id=self.request.user.id,
            fecha_inicio=datos["fecha_inicio"],
            fecha_fin=datos["fecha_fin"],
            finalidad=datos.get("finalidad", ""),
        )
        try:
            self.object = solicitud_servicio().solicitar(dto)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        # FormMixin.form_valid redirige sin volver a guardar el ModelForm.
        return super(CreateView, self).form_valid(form)


class SolicitudDetailView(LoginRequiredMixin, DetailView):
    model = Solicitud
    template_name = "circulacion/solicitud_detail.html"
    context_object_name = "solicitud"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        solicitud = self.object
        usuario = self.request.user
        encargado = usuario.tiene_rol(RolSistema.ENCARGADO)
        supervisor = usuario.tiene_rol(RolSistema.SUPERVISOR)
        pendiente = solicitud.estado == EstadoSolicitud.PENDIENTE
        espera = solicitud.estado == EstadoSolicitud.EN_ESPERA_SUPERVISOR
        ctx.update(
            puede_aprobar=encargado and pendiente,
            puede_aprobar_supervisor=supervisor and espera,
            puede_rechazar=(encargado and pendiente) or (supervisor and espera),
            puede_cancelar=pendiente and solicitud.solicitante_id == usuario.id,
        )
        return ctx


class SolicitudAccionView(LoginRequiredMixin, View):
    """Nunca modifica solicitudes por GET."""
    http_method_names = ["post", "options"]
    accion = None

    def post(self, request, pk):
        solicitud = get_object_or_404(Solicitud, pk=pk)
        usuario = request.user
        encargado = usuario.tiene_rol(RolSistema.ENCARGADO)
        supervisor = usuario.tiene_rol(RolSistema.SUPERVISOR)
        pendiente = solicitud.estado == EstadoSolicitud.PENDIENTE
        espera = solicitud.estado == EstadoSolicitud.EN_ESPERA_SUPERVISOR

        if self.accion == "aprobar":
            if not encargado:
                raise PermissionDenied("Se requiere el rol Encargado.")
            if not pendiente:
                raise PermissionDenied("La solicitud no está pendiente.")
            # Fallar cerrado: no aprobar sin comprobar si el ítem es especial.
            # Cuando Catálogo esté integrado, inyectar su servicio en la fábrica.
            servicio = solicitud_servicio()
            if servicio.aprobacion is None:
                messages.error(request, "Aprobación no disponible hasta integrar Catálogo.")
                return redirect("circulacion:solicitud_detalle", pk=pk)
            operacion = lambda: servicio.aprobar(pk, usuario.id)
        elif self.accion == "aprobar_supervisor":
            if not supervisor or not espera:
                raise PermissionDenied("No puede aprobar esta solicitud como supervisor.")
            operacion = lambda: solicitud_servicio().aprobar_como_supervisor(pk, usuario.id)
        elif self.accion == "rechazar":
            if not ((encargado and pendiente) or (supervisor and espera)):
                raise PermissionDenied("No puede rechazar esta solicitud.")
            motivo = request.POST.get("motivo", "").strip()
            if not motivo:
                messages.error(request, "Debe indicar el motivo del rechazo.")
                return redirect("circulacion:solicitud_detalle", pk=pk)
            operacion = lambda: solicitud_servicio().rechazar(pk, usuario.id, motivo)
        elif self.accion == "cancelar":
            if solicitud.solicitante_id != usuario.id or not pendiente:
                raise PermissionDenied("Solo el propietario puede cancelar una solicitud pendiente.")
            operacion = lambda: solicitud_servicio().cancelar(pk)
        else:
            return HttpResponseNotAllowed(["POST"])

        try:
            operacion()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Operación realizada correctamente.")
        return redirect("circulacion:solicitud_detalle", pk=pk)


class AprobarSolicitudView(SolicitudAccionView):
    accion = "aprobar"


class AprobarSupervisorView(SolicitudAccionView):
    accion = "aprobar_supervisor"


class RechazarSolicitudView(SolicitudAccionView):
    accion = "rechazar"


class CancelarSolicitudView(SolicitudAccionView):
    accion = "cancelar"
