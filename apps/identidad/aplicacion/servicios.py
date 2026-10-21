"""
Capa de APLICACIÓN — casos de uso de Identidad.

Orquesta dominio + puertos (repositorios, hasher, auditoría). No conoce
request, plantillas ni sesiones: eso lo hace la capa de presentación.

API pública que usan los otros contextos (a través de `fabrica.cuenta_servicio()`):
    - consultar_habilitacion(solicitante_id) -> ResultadoHabilitacion   (Circulación)
"""
from abc import ABC, abstractmethod

from apps.auditoria.models import TipoAccion
from apps.common.choices import RolSistema
from apps.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    CuentaInactiva,
    CuentaNoEncontrada,
)
from apps.identidad.dominio.habilitacion import ResultadoHabilitacion
from apps.identidad.dominio.hasher import IPasswordHasher
from apps.identidad.dominio.repositorio import (
    ICuentaRepositorio,
    IPerfilSolicitanteRepositorio,
)

# Hash ficticio para que el tiempo de respuesta sea parecido exista o no el correo
# (evita adivinar qué correos están registrados midiendo el tiempo).
_HASH_FICTICIO = None


class ICuentaServicio(ABC):
    @abstractmethod
    def iniciar_sesion(self, correo, password): ...

    @abstractmethod
    def asignar_rol(self, cuenta_id, rol, actor_id): ...

    @abstractmethod
    def consultar_habilitacion(self, solicitante_id) -> ResultadoHabilitacion: ...


class CuentaServicioAplicacion(ICuentaServicio):
    def __init__(
        self,
        cuenta_repositorio: ICuentaRepositorio,
        perfil_repositorio: IPerfilSolicitanteRepositorio,
        hasher: IPasswordHasher,
        auditoria=None,
    ):
        self._cuentas = cuenta_repositorio
        self._perfiles = perfil_repositorio
        self._hasher = hasher
        self._auditoria = auditoria

    # ------------------------------------------------------------------ #
    # RF-B4: inicio de sesión
    # ------------------------------------------------------------------ #
    def iniciar_sesion(self, correo, password):
        """Devuelve la Cuenta si las credenciales son válidas.

        Lanza CredencialesInvalidas (mensaje genérico, no revela si el correo
        existe) o CuentaInactiva. Abrir la sesión HTTP le toca al controlador.
        """
        cuenta = self._cuentas.por_correo(correo)
        if cuenta is None:
            self._gastar_tiempo_como_si_verificara(password)
            raise CredencialesInvalidas("Correo o contraseña incorrectos.")
        if not cuenta.autenticar(password, self._hasher):
            raise CredencialesInvalidas("Correo o contraseña incorrectos.")
        if not cuenta.is_active:
            raise CuentaInactiva("Tu cuenta está desactivada. Comunícate con el administrador.")
        return cuenta

    def _gastar_tiempo_como_si_verificara(self, password):
        global _HASH_FICTICIO
        if _HASH_FICTICIO is None:
            _HASH_FICTICIO = self._hasher.hashear("contraseña-ficticia")
        self._hasher.verificar(password or "", _HASH_FICTICIO)

    # ------------------------------------------------------------------ #
    # RF-B5: roles
    # ------------------------------------------------------------------ #
    def asignar_rol(self, cuenta_id, rol, actor_id):
        """Asigna un rol a la cuenta. Devuelve False si ya lo tenía.

        Lanza CuentaNoEncontrada o RolInvalido. Deja constancia en auditoría (RF-J2).
        """
        cuenta = self._cuentas.obtener(cuenta_id)
        if cuenta is None:
            raise CuentaNoEncontrada("La cuenta no existe.")
        if not cuenta.asignar_rol(rol):
            return False
        self._cuentas.guardar(cuenta)
        if self._auditoria is not None:
            self._auditoria.registrar(
                actor_id, TipoAccion.CAMBIO_ESTADO, "Cuenta", cuenta.pk,
                f"Rol asignado: {RolSistema(rol).label}",
            )
        return True

    def listar_cuentas(self, q=""):
        return self._cuentas.listar(q)

    # ------------------------------------------------------------------ #
    # RF-B3: ¿puede solicitar? (la usa Circulación)
    # ------------------------------------------------------------------ #
    def consultar_habilitacion(self, solicitante_id) -> ResultadoHabilitacion:
        """¿El solicitante (Cuenta.id) puede pedir préstamos según Identidad?

        Revisa: cuenta existe y activa, tiene PerfilSolicitante, habilitación
        institucional, acta firmada y etiqueta distinta de SANCIONADO/BANEADO.

        Nunca lanza excepción: si algo falla, responde "no habilitado" + motivo,
        para que el Core decida sin try/except.
        """
        cuenta = self._cuentas.obtener(solicitante_id)
        if cuenta is None:
            return ResultadoHabilitacion.no(solicitante_id, "La cuenta no existe.")
        if not cuenta.is_active:
            return ResultadoHabilitacion.no(solicitante_id, "La cuenta está desactivada.")

        perfil = self._perfiles.de_cuenta(cuenta.pk)
        if perfil is None:
            return ResultadoHabilitacion.no(
                solicitante_id, "La cuenta no tiene perfil de solicitante."
            )

        motivos = perfil.motivos_de_inhabilitacion()
        if motivos:
            return ResultadoHabilitacion.no(solicitante_id, *motivos)
        return ResultadoHabilitacion.si(solicitante_id)
