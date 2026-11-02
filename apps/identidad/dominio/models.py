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

from .excepciones import ActaYaFirmada, RolInvalido
from .hasher import IPasswordHasher
from .validadores import (
    validar_celular,
    validar_correo_institucional,
    validar_cui,
    validar_dni,
)

# Roles que son "personal" de la escuela (no solo solicitantes).
ROLES_PERSONAL = (RolSistema.ADMINISTRADOR, RolSistema.ENCARGADO, RolSistema.SUPERVISOR)


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
    dni = models.CharField("DNI", max_length=15, unique=True, validators=[validar_dni])
    # --- VO Contacto embebido ---
    correo = models.EmailField("correo", unique=True, validators=[validar_correo_institucional])
    celular = models.CharField(max_length=20, blank=True, validators=[validar_celular])
    direccion = models.CharField("dirección", max_length=255, blank=True)
    # --- roles del dominio (conjunto) ---
    roles = ArrayField(
        models.CharField(max_length=20, choices=RolSistema.choices),
        default=list,
        blank=True,
        help_text="Conjunto de roles del sistema.",
    )
    # --- Consentimiento de datos personales (RNF-2, Ley 29733) ---
    consentimiento_version = models.CharField(
        "versión del consentimiento de datos", max_length=20, blank=True
    )
    consentimiento_fecha = models.DateTimeField(
        "fecha del consentimiento de datos", null=True, blank=True
    )
    is_active = models.BooleanField("activa", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)

    objects = CuentaManager()

    USERNAME_FIELD = "correo"       # se inicia sesión con el correo
    EMAIL_FIELD = "correo"          # a dónde manda Django el correo de recuperación (RF-B4)
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

    def quitar_rol(self, rol):
        """Saca el rol del conjunto. Devuelve False si no lo tenía (idempotente)."""
        if rol not in RolSistema.values:
            raise RolInvalido(f"Rol no válido: {rol}")
        if not self.tiene_rol(rol):
            return False
        self.roles = [r for r in self.roles if r != rol]
        return True

    def es_personal(self):
        return self.is_superuser or self.tiene_algun_rol(*ROLES_PERSONAL)

    def roles_legibles(self):
        return [RolSistema(r).label for r in (self.roles or []) if r in RolSistema.values]

    def sincronizar_acceso_panel(self):
        """Solo el Administrador entra al panel /admin/ (ahí se configuran las Políticas).

        El superusuario se deja como está: se crea por consola y no depende de roles.
        """
        if not self.is_superuser:
            self.is_staff = self.tiene_rol(RolSistema.ADMINISTRADOR)

    def activar(self):
        if self.is_active:
            return False
        self.is_active = True
        return True

    def desactivar(self):
        """Se desactiva, nunca se borra: préstamos, sanciones y auditoría guardan su id."""
        if not self.is_active:
            return False
        self.is_active = False
        return True

    def actualizar_contacto(self, celular, direccion):
        self.celular = (celular or "").strip()
        self.direccion = (direccion or "").strip()

    def registrar_consentimiento(self, version, fecha):
        self.consentimiento_version = version
        self.consentimiento_fecha = fecha

    def dio_consentimiento(self):
        return bool(self.consentimiento_version and self.consentimiento_fecha)

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
    cui = models.CharField("CUI", max_length=20, blank=True, validators=[validar_cui])
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

    def firmar_acta(self, version, fecha):
        """El acta se firma UNA sola vez (RF-B2): se guarda la versión y la fecha."""
        if self.acta_firmada():
            raise ActaYaFirmada("El acta de responsabilidad ya fue firmada.")
        self.acta_version = version
        self.acta_fecha_firma = fecha

    def cambiar_etiqueta(self, nueva):
        """Devuelve False si ya tenía esa etiqueta (así no se audita nada)."""
        if nueva not in EtiquetaEstado.values:
            raise ValueError(f"Etiqueta no válida: {nueva}")
        if self.etiqueta == nueva:
            return False
        self.etiqueta = nueva
        return True

    def cambiar_habilitacion_institucional(self, habilitado):
        if self.habilitado_institucional == habilitado:
            return False
        self.habilitado_institucional = habilitado
        return True

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
