"""Pantalla del administrador para ver cuentas y asignarles roles (RF-B5)."""
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.auditoria.utils import actor_id_de
from apps.common.choices import RolSistema
from apps.identidad.dominio.excepciones import CuentaNoEncontrada, RolInvalido
from apps.identidad.fabrica import cuenta_servicio

from .forms import AsignarRolForm
from .permisos import RolRequeridoMixin


class CuentaListController(RolRequeridoMixin, View):
    roles_permitidos = [RolSistema.ADMINISTRADOR]
    template_name = "identidad/cuenta_list.html"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        return render(request, self.template_name, {
            "cuentas": cuenta_servicio().listar_cuentas(q),
            "form_rol": AsignarRolForm(),
            "q": q,
        })


class AsignarRolController(RolRequeridoMixin, View):
    roles_permitidos = [RolSistema.ADMINISTRADOR]

    def post(self, request, pk):
        form = AsignarRolForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Elige un rol válido.")
            return redirect("identidad:cuentas")
        rol = form.cleaned_data["rol"]
        try:
            asignado = cuenta_servicio().asignar_rol(pk, rol, actor_id_de(request))
        except (CuentaNoEncontrada, RolInvalido) as error:
            messages.error(request, str(error))
        else:
            etiqueta = RolSistema(rol).label
            if asignado:
                messages.success(request, f"Rol «{etiqueta}» asignado.")
            else:
                messages.info(request, f"La cuenta ya tenía el rol «{etiqueta}».")
        return redirect("identidad:cuentas")
