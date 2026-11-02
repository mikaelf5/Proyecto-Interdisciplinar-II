"""
Cuentas de DEMO: una por rol, con contraseña conocida.

Uso:
    python manage.py seed_cuentas

Se puede correr varias veces: si la cuenta ya existe, la deja como al inicio
(contraseña, roles, activa, perfil). Usa los mismos correos y DNI que
`seed_demo` de Catálogo, así ambos comandos conviven sin duplicar nada.

Las cuentas nuevas se crean con el caso de uso `registrar_cuenta`, igual que
desde la pantalla «Registrar usuario» (acta + consentimiento incluidos).
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

# correo, nombres, dni, roles, perfil (tipo, cui, habilitado) o None
CUENTAS_DEMO = [
    ("admin@demo.pe", "Adriana Administradora", "79000000", [RolSistema.ADMINISTRADOR], None),
    ("encargado@demo.pe", "Elena Encargada", "79000001", [RolSistema.ENCARGADO], None),
    ("supervisor@demo.pe", "Sergio Supervisor", "79000004", [RolSistema.SUPERVISOR], None),
    ("ana@demo.pe", "Ana Alumna", "79000002", [RolSistema.SOLICITANTE],
     (TipoUsuario.ALUMNO, "20230001", True)),
    ("diego@demo.pe", "Diego Docente", "79000003", [RolSistema.SOLICITANTE],
     (TipoUsuario.DOCENTE, "", True)),
    # Para mostrar RF-B3: registrada pero aún no validada por la escuela.
    ("pedro@demo.pe", "Pedro Por Validar", "79000005", [RolSistema.SOLICITANTE],
     (TipoUsuario.ALUMNO, "20230002", False)),
]


class Command(BaseCommand):
    help = "Crea o restablece las cuentas de demo (una por rol, contraseña demo1234)."

    def handle(self, *args, **opciones):
        servicio = cuenta_servicio()
        for correo, nombres, dni, roles, perfil in CUENTAS_DEMO:
            cuenta = Cuenta.objects.filter(correo__iexact=correo).first()
            if cuenta is None:
                servicio.registrar_cuenta(RegistroCuentaDTO(
                    nombres=nombres, dni=dni, correo=correo, password=CLAVE_DEMO,
                    roles=roles, consentimiento_aceptado=True,
                    perfil=PerfilSolicitanteDTO(*perfil, acta_aceptada=True) if perfil else None,
                ), ACTOR_SISTEMA)
                self.stdout.write(f"  creada      {correo}")
            else:
                self._restablecer(cuenta, roles, perfil)
                self.stdout.write(f"  restablecida {correo}")

        self.stdout.write(self.style.SUCCESS(f"\nCuentas de demo listas. Contraseña de todas: {CLAVE_DEMO}"))
        for correo, _, _, roles, _ in CUENTAS_DEMO:
            self.stdout.write(f"  {correo:22} {', '.join(RolSistema(r).label for r in roles)}")

    @transaction.atomic
    def _restablecer(self, cuenta, roles, perfil):
        from apps.identidad.infraestructura.repositorio_django import CuentaRepositorioImpl

        cuenta.set_password(CLAVE_DEMO)
        cuenta.roles = list(roles)
        cuenta.is_active = True
        cuenta.is_superuser = False  # así la demo muestra los permisos POR ROL (seed_demo lo hace superusuario)
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
