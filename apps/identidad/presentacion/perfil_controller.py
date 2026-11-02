"""«Mi perfil»: cada usuario ve sus datos, su estado y corrige su contacto.

También cumple el derecho de ACCESO de la Ley 29733: la persona puede ver
qué datos suyos guarda el sistema y qué aceptó (acta y consentimiento).
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.identidad.dominio.excepciones import DatosInvalidos
from apps.identidad.fabrica import cuenta_servicio

from .forms import ContactoForm


class MiPerfilController(LoginRequiredMixin, View):
    template_name = "identidad/mi_perfil.html"

    def _render(self, request, form):
        servicio = cuenta_servicio()
        cuenta = request.user
        perfil = servicio.perfil_de(cuenta.pk)
        habilitacion = None
        if perfil is not None:
            habilitacion = servicio.consultar_habilitacion(cuenta.pk)  # también refresca la etiqueta
            perfil = servicio.perfil_de(cuenta.pk)
        return render(request, self.template_name, {
            "cuenta": cuenta, "perfil": perfil, "habilitacion": habilitacion, "form": form,
        })

    def get(self, request):
        form = ContactoForm(initial={"celular": request.user.celular, "direccion": request.user.direccion})
        return self._render(request, form)

    def post(self, request):
        form = ContactoForm(request.POST)
        if form.is_valid():
            try:
                cuenta_servicio().actualizar_contacto(
                    request.user.pk, form.cleaned_data["celular"], form.cleaned_data["direccion"])
            except DatosInvalidos as error:
                for campo, mensaje in error.errores.items():
                    form.add_error(campo, mensaje)
            else:
                messages.success(request, "Datos de contacto actualizados.")
                return redirect("identidad:mi_perfil")
        return self._render(request, form)
