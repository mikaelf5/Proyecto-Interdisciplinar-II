"""Pantallas del ADMINISTRADOR: registrar cuentas y gestionarlas (RF-B1, RF-B2, RF-B3, RF-B5)."""
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.auditoria.utils import actor_id_de
from apps.common.choices import RolSistema
from apps.identidad.aplicacion.dtos import PerfilSolicitanteDTO, RegistroCuentaDTO
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.dominio.excepciones import CuentaNoEncontrada, DatosInvalidos, IdentidadError
from apps.identidad.fabrica import cuenta_servicio

from .forms import AsignarRolForm, MotivoForm, PerfilSolicitanteForm, RegistroCuentaForm
from .permisos import RolRequeridoMixin


class _SoloAdministrador(RolRequeridoMixin):
    roles_permitidos = [RolSistema.ADMINISTRADOR]


def _perfil_dto(datos):
    return PerfilSolicitanteDTO(
        tipo=datos.get("tipo") or "",
        cui=datos.get("cui") or "",
        habilitado_institucional=datos.get("habilitado_institucional", False),
        acta_aceptada=datos.get("acta_aceptada", False),
    )


def _errores_al_formulario(form, error):
    """Pone cada error del servicio en su campo (o arriba si el campo no existe)."""
    for campo, mensaje in error.errores.items():
        form.add_error(campo if campo in form.fields else None, mensaje)


class CuentaListController(_SoloAdministrador, View):
    template_name = "identidad/cuenta_list.html"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        rol = request.GET.get("rol", "")
        estado = request.GET.get("estado", "")
        return render(request, self.template_name, {
            "cuentas": cuenta_servicio().listar_cuentas(q, rol=rol, estado=estado),
            "roles": RolSistema.choices,
            "q": q, "rol": rol, "estado": estado,
        })


class RegistrarCuentaController(_SoloAdministrador, View):
    """RF-B1: el administrador registra al usuario (datos + perfil + acta + consentimiento)."""

    template_name = "identidad/cuenta_form.html"

    def _render(self, request, form):
        return render(request, self.template_name, {
            "form": form, "version_acta": VERSION_ACTA,
            "version_consentimiento": VERSION_CONSENTIMIENTO,
        })

    def get(self, request):
        return self._render(request, RegistroCuentaForm())

    def post(self, request):
        form = RegistroCuentaForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            dto = RegistroCuentaDTO(
                nombres=d["nombres"], dni=d["dni"], correo=d["correo"],
                password=d["password1"], celular=d["celular"], direccion=d["direccion"],
                roles=d["roles"], consentimiento_aceptado=d["consentimiento_aceptado"],
                perfil=_perfil_dto(d),
            )
            try:
                cuenta = cuenta_servicio().registrar_cuenta(dto, actor_id_de(request))
            except DatosInvalidos as error:
                _errores_al_formulario(form, error)
            else:
                messages.success(request, f"Cuenta de {cuenta.nombres} registrada.")
                return redirect("identidad:cuenta_detalle", pk=cuenta.pk)
        return self._render(request, form)


class CuentaDetalleController(_SoloAdministrador, View):
    template_name = "identidad/cuenta_detail.html"

    def get(self, request, pk):
        servicio = cuenta_servicio()
        try:
            cuenta = servicio.obtener_cuenta(pk)
        except CuentaNoEncontrada:
            messages.error(request, "La cuenta no existe.")
            return redirect("identidad:cuentas")
        perfil = servicio.perfil_de(cuenta.pk)
        return render(request, self.template_name, {
            "cuenta": cuenta,
            "perfil": perfil,
            "habilitacion": servicio.consultar_habilitacion(cuenta.pk) if perfil else None,
            "form_rol": AsignarRolForm(),
            "form_motivo": MotivoForm(),
            "form_perfil": PerfilSolicitanteForm() if perfil is None else None,
            "es_yo": str(cuenta.pk) == str(request.user.pk),
        })


class _AccionCuentaController(_SoloAdministrador, View):
    """Plantilla de todas las acciones: ejecutar caso de uso -> mensaje -> volver al detalle.

    Los errores del dominio se muestran como mensaje, nunca como error 500.
    """

    def ejecutar(self, request, pk):
        """Devuelve (hubo_cambio, mensaje_si_cambio, mensaje_si_no_cambio)."""
        raise NotImplementedError

    def post(self, request, pk):
        try:
            cambio, si, no = self.ejecutar(request, pk)
        except DatosInvalidos as error:
            for mensaje in error.errores.values():
                messages.error(request, mensaje)
        except IdentidadError as error:
            messages.error(request, str(error))
        else:
            (messages.success if cambio else messages.info)(request, si if cambio else no)
        return redirect("identidad:cuenta_detalle", pk=pk)


class AsignarRolController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        form = AsignarRolForm(request.POST)
        if not form.is_valid():
            return False, "", "Elige un rol válido."
        rol = form.cleaned_data["rol"]
        etiqueta = RolSistema(rol).label
        cambio = cuenta_servicio().asignar_rol(pk, rol, actor_id_de(request))
        return cambio, f"Rol «{etiqueta}» asignado.", f"La cuenta ya tenía el rol «{etiqueta}»."


class QuitarRolController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        form = AsignarRolForm(request.POST)
        if not form.is_valid():
            return False, "", "Elige un rol válido."
        rol = form.cleaned_data["rol"]
        etiqueta = RolSistema(rol).label
        cambio = cuenta_servicio().quitar_rol(pk, rol, actor_id_de(request))
        return cambio, f"Rol «{etiqueta}» quitado.", f"La cuenta no tenía el rol «{etiqueta}»."


class DesactivarCuentaController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        motivo = request.POST.get("motivo", "")
        cambio = cuenta_servicio().desactivar_cuenta(pk, actor_id_de(request), motivo)
        return cambio, "Cuenta desactivada: ya no puede iniciar sesión.", "La cuenta ya estaba inactiva."


class ActivarCuentaController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        cambio = cuenta_servicio().activar_cuenta(pk, actor_id_de(request))
        return cambio, "Cuenta activada.", "La cuenta ya estaba activa."


class HabilitacionController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        habilitar = request.POST.get("habilitado") == "1"
        cambio = cuenta_servicio().cambiar_habilitacion_institucional(
            pk, habilitar, actor_id_de(request), request.POST.get("motivo", ""))
        texto = "confirmada" if habilitar else "retirada"
        return cambio, f"Habilitación institucional {texto}.", "No hubo cambios."


class CompletarPerfilController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        form = PerfilSolicitanteForm(request.POST)
        if not form.is_valid():
            raise DatosInvalidos({c: e[0] for c, e in form.errors.items()})
        cuenta_servicio().completar_perfil(pk, _perfil_dto(form.cleaned_data), actor_id_de(request))
        return True, "Perfil de solicitante creado y acta firmada.", ""


class RecalcularEtiquetaController(_AccionCuentaController):
    def ejecutar(self, request, pk):
        servicio = cuenta_servicio()
        anterior = getattr(servicio.perfil_de(pk), "etiqueta", None)
        nueva = servicio.actualizar_etiqueta(pk)
        if nueva is None:
            return False, "", "La cuenta no tiene perfil de solicitante."
        return nueva != anterior, f"Etiqueta actualizada a {nueva}.", f"La etiqueta sigue siendo {nueva}."
