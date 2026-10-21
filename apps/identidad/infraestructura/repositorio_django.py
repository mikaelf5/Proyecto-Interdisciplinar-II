from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.identidad.dominio.models import Cuenta, PerfilSolicitante
from apps.identidad.dominio.repositorio import (
    ICuentaRepositorio,
    IPerfilSolicitanteRepositorio,
)


class CuentaRepositorioImpl(ICuentaRepositorio):
    def obtener(self, cuenta_id):
        try:
            return Cuenta.objects.filter(pk=cuenta_id).first()
        except (ValueError, ValidationError):  # id que no es un UUID válido
            return None

    def por_correo(self, correo):
        return Cuenta.objects.filter(correo__iexact=(correo or "").strip()).first()

    def guardar(self, cuenta):
        cuenta.save()
        return cuenta

    def listar(self, q=""):
        cuentas = Cuenta.objects.all().order_by("nombres")
        if q:
            cuentas = cuentas.filter(
                Q(nombres__icontains=q) | Q(correo__icontains=q) | Q(dni__icontains=q)
            )
        return cuentas


class PerfilSolicitanteRepositorioImpl(IPerfilSolicitanteRepositorio):
    def de_cuenta(self, cuenta_id):
        try:
            return (
                PerfilSolicitante.objects.select_related("cuenta")
                .filter(cuenta_id=cuenta_id)
                .first()
            )
        except (ValueError, ValidationError):
            return None
