"""
Capa de APLICACIÓN — registro por autoservicio con aprobación del administrador.

Flujo:
    1. solicitar(dto)         -> la persona envía sus datos + documento. Queda PENDIENTE.
                                 Todavía NO existe Cuenta: no puede iniciar sesión.
    2. aprobar(id, dto, actor) -> el Administrador revisa el documento, elige el/los
                                 rol(es) y se crea la Cuenta (+ PerfilSolicitante si
                                 corresponde). Se le avisa por correo.
    3. rechazar(id, motivo, actor) -> queda RECHAZADA con motivo y se le avisa por correo.
                                 Puede volver a enviar otra solicitud.
"""
import logging
from contextlib import nullcontext

from django.utils import timezone

from apps.auditoria.models import TipoAccion
from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.dominio.excepciones import (
    DatosInvalidos,
    MotivoRequerido,
    OperacionNoPermitida,
)
from apps.identidad.dominio.models import (
    Cuenta,
    PerfilSolicitante,
    SolicitudRegistro,
    TipoDocumentoAcreditacion,
)
from apps.identidad.dominio.validadores import (
    error_de,
    validar_celular,
    validar_correo_institucional,
    validar_cui,
    validar_dni,
    validar_documento,
)

logger = logging.getLogger(__name__)


class RegistroServicioAplicacion:
    def __init__(self, solicitudes, cuentas, perfiles, hasher, correo=None,
                 auditoria=None, transaccion=None):
        self._solicitudes = solicitudes      # ISolicitudRegistroRepositorio
        self._cuentas = cuentas              # ICuentaRepositorio
        self._perfiles = perfiles            # IPerfilSolicitanteRepositorio
        self._hasher = hasher
        self._correo = correo                # ICorreoRegistroPuerto (o None)
        self._auditoria = auditoria
        self._transaccion = transaccion or nullcontext

    # ------------------------------------------------------------------ #
    # 1. La persona se registra
    # ------------------------------------------------------------------ #
    def solicitar(self, dto):
        errores = self._validar(dto)
        if errores:
            raise DatosInvalidos(errores)
        ahora = timezone.now()
        solicitud = SolicitudRegistro(
            nombres=dto.nombres.strip(),
            dni=dto.dni.strip(),
            correo=dto.correo.strip().lower(),
            password_hash=self._hasher.hashear(dto.password),
            celular=dto.celular.strip(),
            direccion=dto.direccion.strip(),
            tipo=dto.tipo,
            cui=(dto.cui or "").strip(),
            tipo_documento=dto.tipo_documento,
            documento=dto.documento,
            acta_version=VERSION_ACTA,
            acta_fecha=timezone.localdate(ahora),
            consentimiento_version=VERSION_CONSENTIMIENTO,
            consentimiento_fecha=ahora,
        )
        return self._solicitudes.guardar(solicitud)

    def _validar(self, dto):
        errores = {}
        if not (dto.nombres or "").strip():
            errores["nombres"] = "Ingresa tus nombres y apellidos."

        dni = (dto.dni or "").strip()
        error = error_de(validar_dni, dni)
        if error:
            errores["dni"] = error
        elif self._cuentas.existe_dni(dni):
            errores["dni"] = "Ya existe una cuenta con ese DNI. Si es tuya, inicia sesión."
        elif self._solicitudes.hay_pendiente(dni=dni):
            errores["dni"] = "Ya hay una solicitud en revisión con ese DNI."

        correo = (dto.correo or "").strip().lower()
        error = error_de(validar_correo_institucional, correo) if correo else "Ingresa tu correo."
        if error:
            errores["correo"] = error
        elif self._cuentas.por_correo(correo) is not None:
            errores["correo"] = "Ya existe una cuenta con ese correo. Si es tuya, inicia sesión."
        elif self._solicitudes.hay_pendiente(correo=correo):
            errores["correo"] = "Ya hay una solicitud en revisión con ese correo."

        celular = (dto.celular or "").strip()
        error = error_de(validar_celular, celular) if celular else "Ingresa tu celular."
        if error:
            errores["celular"] = error
        if not (dto.direccion or "").strip():
            errores["direccion"] = "Ingresa tu dirección."

        if dto.tipo not in TipoUsuario.values:
            errores["tipo"] = "Elige si eres alumno, docente o administrativo."
        cui = (dto.cui or "").strip()
        if dto.tipo == TipoUsuario.ALUMNO and not cui:
            errores["cui"] = "El CUI es obligatorio para alumnos."
        elif cui:
            error = error_de(validar_cui, cui)
            if error:
                errores["cui"] = error

        if dto.tipo_documento not in TipoDocumentoAcreditacion.values:
            errores["tipo_documento"] = "Elige qué documento vas a subir."
        if not dto.documento:
            errores["documento"] = "Sube el documento que acredita que eres de la escuela."
        else:
            error = error_de(validar_documento, dto.documento)
            if error:
                errores["documento"] = error

        if not dto.password:
            errores["password1"] = "Ingresa una contraseña."
        if not dto.acta_aceptada:
            errores["acta_aceptada"] = "Debes aceptar el acta de responsabilidad."
        if not dto.consentimiento_aceptado:
            errores["consentimiento_aceptado"] = (
                "Sin tu autorización de datos personales (Ley 29733) no podemos registrarte."
            )
        return errores

    # ------------------------------------------------------------------ #
    # 2. El administrador aprueba
    # ------------------------------------------------------------------ #
    def aprobar(self, solicitud_id, dto, actor_id):
        """Crea la Cuenta con los roles elegidos y avisa por correo. Devuelve la Cuenta."""
        solicitud = self._solicitud(solicitud_id)
        solicitud.exigir_pendiente()
        roles = list(dict.fromkeys(dto.roles or []))
        tipo = dto.tipo or solicitud.tipo
        errores = {}
        if not roles:
            errores["roles"] = "Elige al menos un rol."
        elif any(r not in RolSistema.values for r in roles):
            errores["roles"] = "Hay un rol no válido."
        if RolSistema.SOLICITANTE in roles and tipo not in TipoUsuario.values:
            errores["tipo"] = "Elige el tipo de usuario."
        if RolSistema.SOLICITANTE in roles and tipo == TipoUsuario.ALUMNO and not solicitud.cui:
            errores["tipo"] = "Un alumno necesita CUI y la solicitud no lo trae."
        # Se revisa otra vez: entre que se envió y se aprueba, alguien pudo crear la cuenta.
        if self._cuentas.por_correo(solicitud.correo) is not None:
            errores["correo"] = "Ya existe una cuenta con ese correo: rechaza esta solicitud."
        if self._cuentas.existe_dni(solicitud.dni):
            errores["dni"] = "Ya existe una cuenta con ese DNI: rechaza esta solicitud."
        if errores:
            raise DatosInvalidos(errores)

        ahora = timezone.now()
        with self._transaccion():
            cuenta = Cuenta(nombres=solicitud.nombres, dni=solicitud.dni, correo=solicitud.correo)
            cuenta.password = solicitud.password_hash   # la contraseña que ELLA eligió
            cuenta.actualizar_contacto(solicitud.celular, solicitud.direccion)
            cuenta.registrar_consentimiento(
                solicitud.consentimiento_version, solicitud.consentimiento_fecha
            )
            for rol in roles:
                cuenta.asignar_rol(rol)
            cuenta.sincronizar_acceso_panel()
            self._cuentas.guardar(cuenta)

            if RolSistema.SOLICITANTE in roles:
                perfil = PerfilSolicitante(
                    cuenta=cuenta, tipo=tipo, cui=solicitud.cui,
                    etiqueta=EtiquetaEstado.NUEVO,
                    # El administrador revisó el carné/constancia: queda habilitado.
                    habilitado_institucional=True,
                )
                perfil.firmar_acta(solicitud.acta_version, solicitud.acta_fecha)
                self._perfiles.guardar(perfil)

            solicitud.aprobar(cuenta, actor_id, ahora)
            self._solicitudes.guardar(solicitud)
            self._auditar(actor_id, TipoAccion.APROBACION, "Cuenta", cuenta.pk,
                          "Registro aprobado con roles: "
                          + ", ".join(RolSistema(r).label for r in roles))

        self._enviar(lambda: self._correo.avisar_aprobacion(solicitud, roles))
        return cuenta

    # ------------------------------------------------------------------ #
    # 3. El administrador rechaza
    # ------------------------------------------------------------------ #
    def rechazar(self, solicitud_id, motivo, actor_id):
        motivo = (motivo or "").strip()
        if not motivo:
            raise MotivoRequerido("Indica el motivo del rechazo: se le enviará a la persona.")
        solicitud = self._solicitud(solicitud_id)
        solicitud.rechazar(motivo, actor_id, timezone.now())
        self._solicitudes.guardar(solicitud)
        self._auditar(actor_id, TipoAccion.RECHAZO, "SolicitudRegistro", solicitud.pk,
                      f"Registro rechazado. Motivo: {motivo}")
        self._enviar(lambda: self._correo.avisar_rechazo(solicitud))
        return solicitud

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #
    def listar(self, estado=""):
        return self._solicitudes.listar(estado)

    def obtener(self, solicitud_id):
        return self._solicitud(solicitud_id)

    def contar_pendientes(self):
        return self._solicitudes.contar_pendientes()

    # ------------------------------------------------------------------ #
    # Ayudantes
    # ------------------------------------------------------------------ #
    def _solicitud(self, solicitud_id):
        solicitud = self._solicitudes.obtener(solicitud_id)
        if solicitud is None:
            raise OperacionNoPermitida("La solicitud de registro no existe.")
        return solicitud

    def _enviar(self, accion):
        """Si el correo falla, la decisión YA quedó guardada: no se deshace por eso."""
        if self._correo is None:
            return
        try:
            accion()
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo enviar el correo del resultado del registro.")

    def _auditar(self, actor_id, accion, entidad, entidad_id, motivo):
        if self._auditoria is not None:
            self._auditoria.registrar(actor_id, accion, entidad, entidad_id, motivo)
