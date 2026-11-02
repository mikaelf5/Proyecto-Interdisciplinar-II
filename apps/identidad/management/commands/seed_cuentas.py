"""
Cuentas de DEMO: una por rol, con correo institucional y contraseña conocida.

Uso (cada integrante en su PC, después de `migrate`):
    python manage.py seed_cuentas

Todos obtienen EXACTAMENTE las mismas cuentas (mismo correo, DNI y clave),
así la demo funciona igual en cualquier computadora.

Se puede correr varias veces: si la cuenta ya existe, la deja como al inicio
(contraseña, roles, activa, perfil). Si en tu base quedaron las cuentas
viejas `@demo.pe` (de versiones anteriores de seed_demo), las convierte a
`@unsa.edu.pe` en vez de duplicarlas.

`seed_demo` (Catálogo) llama a este comando: es la única fuente de cuentas demo.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.common.choices import RolSistema, TipoUsuario
from apps.identidad.aplicacion.dtos import PerfilSolicitanteDTO, RegistroCuentaDTO
from apps.identidad.aplicacion.servicios import ACTOR_SISTEMA
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.fabrica import cuenta_servicio
from apps.identidad.models import Cuenta, PerfilSolicitante

CLAVE_DEMO = "demo1234"
DOMINIO_ANTERIOR = "demo.pe"

# correo, nombres, dni, roles, perfil (tipo, cui, habilitado) o None
CUENTAS_DEMO = [
    ("admin@unsa.edu.pe", "Adriana Administradora", "79000000", [RolSistema.ADMINISTRADOR], None),
    ("encargado@unsa.edu.pe", "Elena Encargada", "79000001", [RolSistema.ENCARGADO], None),
    ("supervisor@unsa.edu.pe", "Sergio Supervisor", "79000004", [RolSistema.SUPERVISOR], None),
    ("ana@unsa.edu.pe", "Ana Alumna", "79000002", [RolSistema.SOLICITANTE],
     (TipoUsuario.ALUMNO, "20230001", True)),
    ("diego@unsa.edu.pe", "Diego Docente", "79000003", [RolSistema.SOLICITANTE],
     (TipoUsuario.DOCENTE, "", True)),
    # Para mostrar RF-B3: registrado pero aún no validado por la escuela.
    ("pedro@unsa.edu.pe", "Pedro Por Validar", "79000005", [RolSistema.SOLICITANTE],
     (TipoUsuario.ALUMNO, "20230002", False)),
]

# Atajos para otros comandos (ej. seed_demo): CORREO["ana"] -> "ana@unsa.edu.pe"
CORREO = {c[0].split("@")[0]: c[0] for c in CUENTAS_DEMO}


def _existente(correo, dni):
    """La cuenta demo que ya está en la base: por correo nuevo, por el @demo.pe viejo o por DNI."""
    anterior = f"{correo.split('@')[0]}@{DOMINIO_ANTERIOR}"
    return (Cuenta.objects.filter(correo__iexact=correo).first()
            or Cuenta.objects.filter(correo__iexact=anterior).first()
            or Cuenta.objects.filter(dni=dni).first())


class Command(BaseCommand):
    help = "Crea o restablece las cuentas de demo (una por rol, @unsa.edu.pe, contraseña demo1234)."

    def handle(self, *args, **opciones):
        servicio = cuenta_servicio()
        for correo, nombres, dni, roles, perfil in CUENTAS_DEMO:
            cuenta = _existente(correo, dni)
            if cuenta is None:
                servicio.registrar_cuenta(RegistroCuentaDTO(
                    nombres=nombres, dni=dni, correo=correo, password=CLAVE_DEMO,
                    roles=roles, consentimiento_aceptado=True,
                    perfil=PerfilSolicitanteDTO(*perfil, acta_aceptada=True) if perfil else None,
                ), ACTOR_SISTEMA)
                self.stdout.write(f"  creada        {correo}")
            else:
                antes = cuenta.correo
                self._restablecer(cuenta, correo, roles, perfil)
                detalle = f"  (antes {antes})" if antes.lower() != correo else ""
                self.stdout.write(f"  restablecida  {correo}{detalle}")

        self.stdout.write(self.style.SUCCESS(f"\nCuentas de demo listas. Contraseña de todas: {CLAVE_DEMO}"))
        for correo, _, _, roles, _ in CUENTAS_DEMO:
            self.stdout.write(f"  {correo:24} {', '.join(RolSistema(r).label for r in roles)}")

    @transaction.atomic
    def _restablecer(self, cuenta, correo, roles, perfil):
        from apps.identidad.infraestructura.repositorio_django import CuentaRepositorioImpl

        cuenta.correo = correo
        cuenta.set_password(CLAVE_DEMO)
        cuenta.roles = list(roles)
        cuenta.is_active = True
        cuenta.is_superuser = False  # así la demo muestra los permisos POR ROL
        cuenta.sincronizar_acceso_panel()
        if not cuenta.dio_consentimiento():
            cuenta.registrar_consentimiento(VERSION_CONSENTIMIENTO, timezone.now())
        CuentaRepositorioImpl().guardar(cuenta)
        if perfil:
            tipo, cui, habilitado = perfil
            obj, _ = PerfilSolicitante.objects.get_or_create(cuenta=cuenta, defaults={"tipo": tipo})
            obj.tipo, obj.cui, obj.habilitado_institucional = tipo, cui, habilitado
            if not obj.acta_firmada():
                obj.firmar_acta(VERSION_ACTA, timezone.localdate())
            obj.save()
