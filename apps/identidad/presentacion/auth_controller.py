"""
Capa de PRESENTACIÓN — AuthController.

Recibe el formulario, llama al caso de uso `iniciar_sesion` y, si todo está
bien, abre la sesión HTTP de Django. No contiene reglas de negocio.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.identidad.dominio.excepciones import CredencialesInvalidas, CuentaInactiva
from apps.identidad.fabrica import cuenta_servicio

from .forms import LoginForm


class AuthController(View):
    """GET muestra la pantalla de login; POST inicia sesión."""

    template_name = "identidad/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(self._destino(request))
        return render(request, self.template_name, {"form": LoginForm(), "next": request.GET.get("next", "")})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                cuenta = cuenta_servicio().iniciar_sesion(
                    form.cleaned_data["correo"], form.cleaned_data["password"]
                )
            except (CredencialesInvalidas, CuentaInactiva) as error:
                form.add_error(None, str(error))
            else:
                login(request, cuenta, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, f"Bienvenido(a), {cuenta.nombres}.")
                return redirect(self._destino(request))
        return render(
            request, self.template_name,
            {"form": form, "next": request.POST.get("next", "")},
            status=200,
        )

    @staticmethod
    def _destino(request):
        """Vuelve a la página que pidió el login (?next=) solo si es de nuestro sitio."""
        siguiente = request.POST.get("next") or request.GET.get("next")
        if siguiente and url_has_allowed_host_and_scheme(
            siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return siguiente
        return resolve_url(settings.LOGIN_REDIRECT_URL)


class LogoutController(View):
    """Cierra la sesión. Solo por POST (un enlace GET podría dispararse sin querer)."""

    def post(self, request):
        logout(request)
        messages.info(request, "Cerraste sesión.")
        return redirect(settings.LOGOUT_REDIRECT_URL)
