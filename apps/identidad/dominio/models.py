"""
Capa de DOMINIO — Contexto Identidad y Acceso (Supporting).

- Cuenta: es el AUTH_USER_MODEL. Agrega el VO Contacto (correo/celular/direccion)
  y el conjunto de roles del sistema.
- PerfilSolicitante: datos del solicitante, enlazado 1-a-1 con una Cuenta.
  Como es el mismo contexto, aquí SÍ usamos OneToOne (no UUID).

Regla de la capa: los métodos de dominio validan y cambian el estado en memoria,
pero NO guardan. Guardar es trabajo del repositorio (capa de infraestructura),
que invoca el servicio de aplicación.
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

from .excepciones import RolInvalido
from .hasher import IPasswordHasher


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
        app_label = "identidad"
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"
        ordering = ["correo"]

    def __str__(self):
        return f"{self.nombres} <{self.correo}>"

    # ---------- Métodos del dominio ----------
    def tiene_rol(self, rol):
        return rol in (self.roles or [])

    def tiene_algun_rol(self, *roles):
        return any(self.tiene_rol(r) for r in roles)

    def asignar_rol(self, rol):
        """Agrega el rol al conjunto. Devuelve False si ya lo tenía (idempotente)."""
        if rol not in RolSistema.values:
            raise RolInvalido(f"Rol no válido: {rol}")
        if self.tiene_rol(rol):
            return False
        self.roles = (self.roles or []) + [rol]
        return True

    def autenticar(self, password, hasher: IPasswordHasher):
        """Verifica la contraseña con el hasher que se le inyecte.

        El dominio no sabe CÓMO se hashea (eso es infraestructura): solo pide
        a un IPasswordHasher que compare la contraseña con el hash guardado.
        """
        if not password or not self.password:
            return False
        return hasher.verificar(password, self.password)

    def cambiar_password(self, password_nueva, hasher: IPasswordHasher):
        self.password = hasher.hashear(password_nueva)


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
        app_label = "identidad"
        verbose_name = "perfil de solicitante"
        verbose_name_plural = "perfiles de solicitantes"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Perfil de {self.cuenta.nombres} ({self.get_tipo_display()})"

    def acta_firmada(self):
        return bool(self.acta_version and self.acta_fecha_firma)

    def motivos_de_inhabilitacion(self):
        """Lista de razones por las que NO puede solicitar (vacía = habilitado).

        Reglas: RF-B3 (condición institucional), RF-B2 (acta firmada),
        RF-B6/RF-G2 (etiqueta sancionado/baneado).
        """
        motivos = []
        if not self.habilitado_institucional:
            motivos.append("No está habilitado por su condición institucional.")
        if not self.acta_firmada():
            motivos.append("No ha firmado el acta de responsabilidad.")
        if self.etiqueta == EtiquetaEstado.SANCIONADO:
            motivos.append("Tiene una sanción vigente.")
        elif self.etiqueta == EtiquetaEstado.BANEADO:
            motivos.append("Está baneado del sistema.")
        return motivos

    def esta_habilitado(self):
        return not self.motivos_de_inhabilitacion()
