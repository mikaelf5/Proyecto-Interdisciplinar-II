"""Registro por autoservicio.

- Pantallas PÚBLICAS: la persona envía su solicitud (datos + documento).
- Pantallas del ADMINISTRADOR: revisa el documento, aprueba (elige roles) o rechaza.
"""
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.auditoria.utils import actor_id_de
from apps.common.choices import RolSistema
from apps.identidad.aplicacion.dtos import AprobacionRegistroDTO, SolicitudRegistroDTO
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.dominio.excepciones import DatosInvalidos, IdentidadError
from apps.identidad.dominio.models import EstadoRegistro
from apps.identidad.fabrica import registro_servicio

from .cuenta_controller import _errores_al_formulario
from .forms import AprobarRegistroForm, MotivoForm, SolicitudRegistroForm
from .permisos import RolRequeridoMixin


# ---------------------------------------------------------------------- #
# Público
# ---------------------------------------------------------------------- #
class RegistroPublicoController(View):
    template_name = "identidad/registro_form.html"

    def _render(self, request, form):
        return render(request, self.template_name, {
            "form": form, "version_acta": VERSION_ACTA,
            "version_consentimiento": VERSION_CONSENTIMIENTO,
        })

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("home")
        return self._render(request, SolicitudRegistroForm())

    def post(self, request):
        form = SolicitudRegistroForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.cleaned_data
            dto = SolicitudRegistroDTO(
                nombres=d["nombres"], dni=d["dni"], correo=d["correo"], password=d["password1"],
                celular=d["celular"], direccion=d["direccion"], tipo=d["tipo"], cui=d["cui"],
                tipo_documento=d["tipo_documento"], documento=d["documento"],
                acta_aceptada=d["acta_aceptada"],
                consentimiento_aceptado=d["consentimiento_aceptado"],
            )
            try:
                registro_servicio().solicitar(dto)
            except DatosInvalidos as error:
                _errores_al_formulario(form, error)
            else:
                return redirect("identidad:registro_enviado")
        return self._render(request, form)


class RegistroEnviadoController(View):
    def get(self, request):
        return render(request, "identidad/registro_enviado.html")


# ---------------------------------------------------------------------- #
# Administrador
# ---------------------------------------------------------------------- #
class _SoloAdministrador(RolRequeridoMixin):
    roles_permitidos = [RolSistema.ADMINISTRADOR]


class SolicitudListController(_SoloAdministrador, View):
    def get(self, request):
        estado = request.GET.get("estado", EstadoRegistro.PENDIENTE)
        if estado not in EstadoRegistro.values:
            estado = ""
        return render(request, "identidad/solicitud_list.html", {
            "solicitudes": registro_servicio().listar(estado),
            "estado": estado, "estados": EstadoRegistro.choices,
        })


class SolicitudDetalleController(_SoloAdministrador, View):
    template_name = "identidad/solicitud_detail.html"

    def _render(self, request, solicitud, form_aprobar=None, form_rechazar=None):
        return render(request, self.template_name, {
            "solicitud": solicitud,
            "form_aprobar": form_aprobar or AprobarRegistroForm(initial={
                "roles": [RolSistema.SOLICITANTE], "tipo": solicitud.tipo}),
            "form_rechazar": form_rechazar or MotivoForm(),
        })

    def get(self, request, pk):
        try:
            solicitud = registro_servicio().obtener(pk)
        except IdentidadError as error:
            messages.error(request, str(error))
            return redirect("identidad:solicitudes")
        return self._render(request, solicitud)


class AprobarSolicitudController(SolicitudDetalleController):
    def post(self, request, pk):
        servicio = registro_servicio(request.build_absolute_uri(reverse("identidad:login")))
        form = AprobarRegistroForm(request.POST)
        try:
            solicitud = servicio.obtener(pk)
            if form.is_valid():
                cuenta = servicio.aprobar(pk, AprobacionRegistroDTO(
                    roles=form.cleaned_data["roles"], tipo=form.cleaned_data["tipo"],
                ), actor_id_de(request))
                messages.success(request, f"Registro aprobado: se creó la cuenta de {cuenta.nombres} "
                                          "y se le avisó por correo.")
                return redirect("identidad:cuenta_detalle", pk=cuenta.pk)
        except DatosInvalidos as error:
            _errores_al_formulario(form, error)
        except IdentidadError as error:
            messages.error(request, str(error))
            return redirect("identidad:solicitudes")
        return self._render(request, solicitud, form_aprobar=form)


class RechazarSolicitudController(SolicitudDetalleController):
    def post(self, request, pk):
        try:
            registro_servicio().rechazar(pk, request.POST.get("motivo", ""), actor_id_de(request))
        except IdentidadError as error:
            messages.error(request, str(error))
            return redirect("identidad:solicitud_detalle", pk=pk)
        messages.success(request, "Solicitud rechazada; se le avisó por correo con el motivo.")
        return redirect("identidad:solicitudes")


class DocumentoSolicitudController(_SoloAdministrador, View):
    """El documento tiene datos personales: NO se publica en /media/, se entrega solo al admin."""

    def get(self, request, pk):
        try:
            solicitud = registro_servicio().obtener(pk)
        except IdentidadError:
            raise Http404
        if not solicitud.documento:
            raise Http404
        try:
            archivo = solicitud.documento.open("rb")
        except FileNotFoundError:
            raise Http404
        return FileResponse(archivo, filename=solicitud.documento.name.rsplit("/", 1)[-1])
