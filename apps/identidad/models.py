"""
Contexto: Identidad y Acceso (Supporting).

- Cuenta: es el AUTH_USER_MODEL. Login, hashing de contraseña y sesión los da
  Django gratis. El VO Contacto (correo/celular/direccion) va embebido.
- PerfilSolicitante: datos del solicitante; enlazado 1-a-1 con una Cuenta.
  Como es el mismo contexto, aquí SÍ usamos ForeignKey/OneToOne (no UUID).
"""
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.common.models import BaseModel


class CuentaManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, correo, nombres, dni, password=None, **extra):
        if not correo:
            raise ValueError("La cuenta necesita un correo.")
        cuenta = self.model(
            correo=self.normalize_email(correo),
            nombres=nombres,
            dni=dni,
            **extra,
        )
        cuenta.set_password(password)  # aquí se hashea la contraseña
        cuenta.save(using=self._db)
        return cuenta

    def create_superuser(self, correo, nombres, dni, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Un superusuario debe tener is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Un superusuario debe tener is_superuser=True.")
        return self.create_user(correo, nombres, dni, password, **extra)


class Cuenta(AbstractBaseUser, PermissionsMixin, BaseModel):
    nombres = models.CharField(max_length=150)
    dni = models.CharField(max_length=15, unique=True)
    # --- VO Contacto embebido ---
    correo = models.EmailField("correo", unique=True)
    celular = models.CharField(max_length=20, blank=True)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    # --- roles del dominio (conjunto) ---
    roles = ArrayField(
        models.CharField(max_length=20, choices=RolSistema.choices),
        default=list,
        blank=True,
        help_text="Conjunto de roles del sistema.",
    )
    is_active = models.BooleanField("activa", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)

    objects = CuentaManager()

    USERNAME_FIELD = "correo"       # se inicia sesión con el correo
    REQUIRED_FIELDS = ["nombres", "dni"]

    class Meta:
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"
        ordering = ["correo"]

    def __str__(self):
        return f"{self.nombres} <{self.correo}>"

    # ---------- Métodos del dominio ----------
    def tiene_rol(self, rol):
        return rol in (self.roles or [])

    def asignar_rol(self, rol):
        if rol not in RolSistema.values:
            raise ValueError(f"Rol no válido: {rol}")
        if rol not in (self.roles or []):
            self.roles = (self.roles or []) + [rol]
            self.save(update_fields=["roles"])

    def autenticar(self, password):
        """El dominio pide autenticar(); Django ya verifica el hash."""
        return self.check_password(password)


class PerfilSolicitante(BaseModel):
    cuenta = models.OneToOneField(
        Cuenta, on_delete=models.CASCADE, related_name="perfil"
    )
    tipo = models.CharField(max_length=20, choices=TipoUsuario.choices)
    cui = models.CharField(max_length=20, blank=True)
    # --- VO ActaResponsabilidad embebido ---
    acta_version = models.CharField("versión del acta", max_length=20, blank=True)
    acta_fecha_firma = models.DateField(
        "fecha de firma del acta", null=True, blank=True
    )
    etiqueta = models.CharField(
        max_length=20, choices=EtiquetaEstado.choices, default=EtiquetaEstado.NUEVO
    )
    habilitado_institucional = models.BooleanField(default=False)

    class Meta:
        verbose_name = "perfil de solicitante"
        verbose_name_plural = "perfiles de solicitantes"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Perfil de {self.cuenta.nombres} ({self.get_tipo_display()})"

    def esta_habilitado(self):
        """Habilitado si la institución lo permite y no está sancionado/baneado."""
        bloqueado = {EtiquetaEstado.SANCIONADO, EtiquetaEstado.BANEADO}
        return self.habilitado_institucional and self.etiqueta not in bloqueado
