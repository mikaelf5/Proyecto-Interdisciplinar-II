from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.identidad.dominio.models import (
    Cuenta,
    EstadoRegistro,
    PerfilSolicitante,
    SolicitudRegistro,
)
from apps.identidad.dominio.repositorio import (
    ICuentaRepositorio,
    IPerfilSolicitanteRepositorio,
    ISolicitudRegistroRepositorio,
)

from .acceso_panel import sincronizar_grupo_administradores


class CuentaRepositorioImpl(ICuentaRepositorio):
    def obtener(self, cuenta_id):
        try:
            return Cuenta.objects.filter(pk=cuenta_id).first()
        except (ValueError, ValidationError):  # id que no es un UUID válido
            return None

    def por_correo(self, correo):
        return Cuenta.objects.filter(correo__iexact=(correo or "").strip()).first()

    def existe_dni(self, dni):
        return Cuenta.objects.filter(dni=(dni or "").strip()).exists()

    def contar_activas_con_rol(self, rol):
        # `roles__contains` usa el operador @> del ArrayField de PostgreSQL.
        return Cuenta.objects.filter(is_active=True, roles__contains=[rol]).count()

    def guardar(self, cuenta):
        cuenta.save()
        sincronizar_grupo_administradores(cuenta)
        return cuenta

    def listar(self, q="", rol="", estado=""):
        cuentas = Cuenta.objects.select_related("perfil").order_by("nombres")
        if q:
            cuentas = cuentas.filter(
                Q(nombres__icontains=q) | Q(correo__icontains=q) | Q(dni__icontains=q)
            )
        if rol:
            cuentas = cuentas.filter(roles__contains=[rol])
        if estado == "activas":
            cuentas = cuentas.filter(is_active=True)
        elif estado == "inactivas":
            cuentas = cuentas.filter(is_active=False)
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

    def guardar(self, perfil):
        perfil.save()
        return perfil

    def todos(self):
        return PerfilSolicitante.objects.select_related("cuenta").all()


class SolicitudRegistroRepositorioImpl(ISolicitudRegistroRepositorio):
    def obtener(self, solicitud_id):
        try:
            return SolicitudRegistro.objects.filter(pk=solicitud_id).first()
        except (ValueError, ValidationError):
            return None

    def hay_pendiente(self, correo="", dni=""):
        pendientes = SolicitudRegistro.objects.filter(estado=EstadoRegistro.PENDIENTE)
        filtro = Q()
        if correo:
            filtro |= Q(correo__iexact=correo.strip())
        if dni:
            filtro |= Q(dni=dni.strip())
        return bool(filtro) and pendientes.filter(filtro).exists()

    def ultima_por_correo(self, correo):
        return (SolicitudRegistro.objects
                .filter(correo__iexact=(correo or "").strip())
                .order_by("-creado_en").first())

    def guardar(self, solicitud):
        solicitud.save()
        return solicitud

    def listar(self, estado=""):
        solicitudes = SolicitudRegistro.objects.order_by("-creado_en")
        if estado:
            solicitudes = solicitudes.filter(estado=estado)
        return solicitudes

    def contar_pendientes(self):
        return SolicitudRegistro.objects.filter(estado=EstadoRegistro.PENDIENTE).count()
