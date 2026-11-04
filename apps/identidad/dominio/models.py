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
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.common.models import BaseModel

from .excepciones import ActaYaFirmada, RolInvalido, SolicitudYaRevisada
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
    correo = models.EmailField("correo", unique=True)
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


# ====================================================================== #
# Registro por autoservicio: la persona llena el formulario y el
# Administrador lo aprueba (crea la Cuenta y le da el rol) o lo rechaza.
# ====================================================================== #
class EstadoRegistro(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    APROBADA = "APROBADA", "Aprobada"
    RECHAZADA = "RECHAZADA", "Rechazada"


class TipoDocumentoAcreditacion(models.TextChoices):
    CARNE_UNIVERSITARIO = "CARNE_UNIVERSITARIO", "Carné universitario vigente"
    CONSTANCIA_MATRICULA = "CONSTANCIA_MATRICULA", "Constancia de matrícula"
    OTRO = "OTRO", "Otro documento institucional"


def _ruta_documento(instancia, nombre_original):
    """Se guarda con un nombre aleatorio: el nombre original puede traer datos personales."""
    extension = nombre_original.rsplit(".", 1)[-1].lower() if "." in nombre_original else "bin"
    return f"registro/{uuid.uuid4().hex}.{extension}"


class SolicitudRegistro(BaseModel):
    """Lo que la persona envía al registrarse sola. NO es una Cuenta todavía.

    ¿Por qué un agregado aparte y no una Cuenta inactiva?
    - La tabla de cuentas solo guarda personas aprobadas: nadie sin revisar
      aparece en listados, reportes ni búsquedas de solicitantes.
    - "Inactiva" ya significa "desactivada por el administrador"; mezclar los
      dos casos confundiría el login y la auditoría.
    - Si la rechazan, el correo y el DNI quedan libres para volver a intentarlo.
    La contraseña se guarda YA hasheada; al aprobar, el hash pasa a la Cuenta.
    """

    nombres = models.CharField(max_length=150)
    dni = models.CharField("DNI", max_length=15, validators=[validar_dni])
    correo = models.EmailField("correo", validators=[validar_correo_institucional])
    password_hash = models.CharField(max_length=128)
    celular = models.CharField(max_length=20, validators=[validar_celular])
    direccion = models.CharField("dirección", max_length=255)
    tipo = models.CharField("tipo declarado", max_length=20, choices=TipoUsuario.choices)
    cui = models.CharField("CUI", max_length=20, blank=True, validators=[validar_cui])
    tipo_documento = models.CharField(
        "documento que acredita", max_length=30, choices=TipoDocumentoAcreditacion.choices
    )
    documento = models.FileField("archivo del documento", upload_to=_ruta_documento)
    acta_version = models.CharField("versión del acta", max_length=20)
    acta_fecha = models.DateField("fecha de aceptación del acta")
    consentimiento_version = models.CharField("versión del consentimiento", max_length=20)
    consentimiento_fecha = models.DateTimeField("fecha del consentimiento")
    estado = models.CharField(
        max_length=20, choices=EstadoRegistro.choices, default=EstadoRegistro.PENDIENTE
    )
    motivo_rechazo = models.CharField(max_length=500, blank=True)
    revisado_por_id = models.UUIDField(null=True, blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    cuenta = models.OneToOneField(
        Cuenta, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="solicitud_registro", help_text="Cuenta creada al aprobar.",
    )

    class Meta:
        app_label = "identidad"
        verbose_name = "solicitud de registro"
        verbose_name_plural = "solicitudes de registro"
        ordering = ["-creado_en"]
        constraints = [
            # Una sola solicitud PENDIENTE por correo y por DNI (las rechazadas no cuentan).
            models.UniqueConstraint(
                fields=["correo"], condition=models.Q(estado="PENDIENTE"),
                name="unique_registro_pendiente_por_correo",
            ),
            models.UniqueConstraint(
                fields=["dni"], condition=models.Q(estado="PENDIENTE"),
                name="unique_registro_pendiente_por_dni",
            ),
        ]

    def __str__(self):
        return f"Solicitud de {self.nombres} <{self.correo}> ({self.get_estado_display()})"

    def esta_pendiente(self):
        return self.estado == EstadoRegistro.PENDIENTE

    def exigir_pendiente(self):
        if not self.esta_pendiente():
            raise SolicitudYaRevisada(
                f"La solicitud ya fue {self.get_estado_display().lower()}."
            )

    def aprobar(self, cuenta, revisor_id, fecha):
        self.exigir_pendiente()
        self.estado = EstadoRegistro.APROBADA
        self.cuenta = cuenta
        self.revisado_por_id = revisor_id
        self.fecha_revision = fecha

    def rechazar(self, motivo, revisor_id, fecha):
        self.exigir_pendiente()
        self.estado = EstadoRegistro.RECHAZADA
        self.motivo_rechazo = motivo
        self.revisado_por_id = revisor_id
        self.fecha_revision = fecha
