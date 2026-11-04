"""
Capa de APLICACIÓN — casos de uso de Identidad.

Orquesta dominio + puertos (repositorios, hasher, auditoría, sanciones,
historial de préstamos). No conoce request, plantillas ni sesiones: eso lo
hace la capa de presentación.

API pública que usan los otros contextos (a través de `fabrica.cuenta_servicio()`):
    - consultar_habilitacion(solicitante_id) -> ResultadoHabilitacion   (Circulación)
    - tipo_usuario_de(cuenta_id) -> "ALUMNO" | "DOCENTE" | "ADMINISTRATIVO" | None
                                                                (Políticas, Reservas)
    - actualizar_etiqueta(cuenta_id) -> EtiquetaEstado | None   (Sanciones, Circulación)
"""
import uuid
from abc import ABC, abstractmethod
from contextlib import nullcontext

from django.utils import timezone

from apps.auditoria.models import TipoAccion
from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.dominio.etiquetas import calcular_etiqueta
from apps.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    CuentaInactiva,
    CuentaNoEncontrada,
    DatosInvalidos,
    MotivoRequerido,
    OperacionNoPermitida,
    RegistroNoAprobado,
)
from apps.identidad.dominio.habilitacion import ResultadoHabilitacion
from apps.identidad.dominio.hasher import IPasswordHasher
from apps.identidad.dominio.models import Cuenta, PerfilSolicitante
from apps.identidad.dominio.repositorio import (
    ICuentaRepositorio,
    IPerfilSolicitanteRepositorio,
)
from apps.identidad.dominio.validadores import (
    error_de,
    validar_celular,
    validar_cui,
    validar_dni,
)

# Hash ficticio para que el tiempo de respuesta sea parecido exista o no el correo
# (evita adivinar qué correos están registrados midiendo el tiempo).
_HASH_FICTICIO = None

# Actor de las acciones que hace el propio sistema (ej. recalcular etiquetas).
ACTOR_SISTEMA = uuid.UUID(int=0)

# Préstamos devueltos a tiempo para ser FRECUENTE si no se configura otra cosa.
UMBRAL_FRECUENTE_POR_DEFECTO = 5


class ICuentaServicio(ABC):
    @abstractmethod
    def iniciar_sesion(self, correo, password): ...

    @abstractmethod
    def registrar_cuenta(self, dto, actor_id): ...

    @abstractmethod
    def asignar_rol(self, cuenta_id, rol, actor_id): ...

    @abstractmethod
    def quitar_rol(self, cuenta_id, rol, actor_id): ...

    @abstractmethod
    def consultar_habilitacion(self, solicitante_id) -> ResultadoHabilitacion: ...

    @abstractmethod
    def tipo_usuario_de(self, cuenta_id): ...

    @abstractmethod
    def actualizar_etiqueta(self, cuenta_id): ...


class CuentaServicioAplicacion(ICuentaServicio):
    def __init__(
        self,
        cuenta_repositorio: ICuentaRepositorio,
        perfil_repositorio: IPerfilSolicitanteRepositorio,
        hasher: IPasswordHasher,
        auditoria=None,
        sanciones=None,
        historial=None,
        umbral_frecuente=UMBRAL_FRECUENTE_POR_DEFECTO,
        transaccion=None,
        solicitudes=None,
    ):
        self._cuentas = cuenta_repositorio
        self._perfiles = perfil_repositorio
        self._hasher = hasher
        self._auditoria = auditoria
        self._sanciones = sanciones          # ISancionesPuerto (o None)
        self._historial = historial          # IHistorialPrestamosPuerto (o None)
        self._umbral_frecuente = umbral_frecuente
        # En producción la fábrica inyecta transaction.atomic; en pruebas sin BD no hace nada.
        self._transaccion = transaccion or nullcontext
        # ISolicitudRegistroRepositorio: para avisar en el login si su registro sigue en revisión.
        self._solicitudes = solicitudes

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
            self._revisar_registro_sin_aprobar(correo, password)
            self._gastar_tiempo_como_si_verificara(password)
            raise CredencialesInvalidas("Correo o contraseña incorrectos.")
        if not cuenta.autenticar(password, self._hasher):
            raise CredencialesInvalidas("Correo o contraseña incorrectos.")
        if not cuenta.is_active:
            raise CuentaInactiva("Tu cuenta está desactivada. Comunícate con el administrador.")
        return cuenta

    def _revisar_registro_sin_aprobar(self, correo, password):
        """Si se registró sola y aún no la aprueban (o la rechazaron), se lo decimos.

        Solo si la contraseña coincide: así nadie averigua el estado de un
        registro ajeno probando correos.
        """
        if self._solicitudes is None:
            return
        solicitud = self._solicitudes.ultima_por_correo(correo)
        if solicitud is None or not self._hasher.verificar(password or "", solicitud.password_hash):
            return
        if solicitud.esta_pendiente():
            raise RegistroNoAprobado(
                "Tu solicitud de registro está en revisión. Te avisaremos por correo "
                "cuando el administrador la apruebe."
            )
        if solicitud.motivo_rechazo:
            raise RegistroNoAprobado(
                f"Tu solicitud de registro fue rechazada: {solicitud.motivo_rechazo} "
                "Puedes enviar una nueva solicitud."
            )

    def _gastar_tiempo_como_si_verificara(self, password):
        global _HASH_FICTICIO
        if _HASH_FICTICIO is None:
            _HASH_FICTICIO = self._hasher.hashear("contraseña-ficticia")
        self._hasher.verificar(password or "", _HASH_FICTICIO)

    # ------------------------------------------------------------------ #
    # RF-B1 + RF-B2 + RNF-2: registro (lo hace el administrador)
    # ------------------------------------------------------------------ #
    def registrar_cuenta(self, dto, actor_id):
        """Crea la Cuenta y, si es solicitante, su PerfilSolicitante con el acta firmada.

        Todo o nada (transacción). Lanza DatosInvalidos con un error por campo.
        Guarda la versión y la fecha del acta y del consentimiento de datos.
        """
        roles = list(dict.fromkeys(dto.roles or []))
        errores = self._validar_registro(dto, roles)
        if errores:
            raise DatosInvalidos(errores)

        ahora = timezone.now()
        with self._transaccion():
            cuenta = Cuenta(
                nombres=dto.nombres.strip(),
                dni=dto.dni.strip(),
                correo=dto.correo.strip().lower(),
            )
            cuenta.actualizar_contacto(dto.celular, dto.direccion)
            cuenta.password = self._hasher.hashear(dto.password)
            for rol in roles:
                cuenta.asignar_rol(rol)
            cuenta.sincronizar_acceso_panel()
            cuenta.registrar_consentimiento(VERSION_CONSENTIMIENTO, ahora)
            self._cuentas.guardar(cuenta)

            if RolSistema.SOLICITANTE in roles:
                self._crear_perfil(cuenta, dto.perfil, timezone.localdate(ahora))

            self._auditar(actor_id, cuenta.pk, "Cuenta registrada con roles: "
                          + ", ".join(RolSistema(r).label for r in roles))
        return cuenta

    def _validar_registro(self, dto, roles):
        errores = {}
        if not (dto.nombres or "").strip():
            errores["nombres"] = "Ingresa los nombres y apellidos."
        dni = (dto.dni or "").strip()
        error = error_de(validar_dni, dni)
        if error:
            errores["dni"] = error
        elif self._cuentas.existe_dni(dni):
            errores["dni"] = "Ya existe una cuenta con ese DNI."
        correo = (dto.correo or "").strip()
        if not correo:
            errores["correo"] = "Ingresa el correo."
        elif self._cuentas.por_correo(correo) is not None:
            errores["correo"] = "Ya existe una cuenta con ese correo."
        if dto.celular:
            error = error_de(validar_celular, dto.celular.strip())
            if error:
                errores["celular"] = error
        if not dto.password:
            errores["password1"] = "Ingresa una contraseña inicial."
        if not roles:
            errores["roles"] = "Elige al menos un rol."
        elif any(r not in RolSistema.values for r in roles):
            errores["roles"] = "Hay un rol no válido."
        if not dto.consentimiento_aceptado:
            errores["consentimiento_aceptado"] = (
                "Sin el consentimiento de datos personales (Ley 29733) no se puede registrar."
            )
        if RolSistema.SOLICITANTE in roles:
            errores.update(self._validar_perfil(dto.perfil))
        return errores

    @staticmethod
    def _validar_perfil(perfil):
        errores = {}
        if perfil is None or perfil.tipo not in TipoUsuario.values:
            errores["tipo"] = "Elige el tipo de usuario (alumno, docente o administrativo)."
            return errores
        cui = (perfil.cui or "").strip()
        if perfil.tipo == TipoUsuario.ALUMNO and not cui:
            errores["cui"] = "El CUI es obligatorio para alumnos."
        elif cui:
            error = error_de(validar_cui, cui)
            if error:
                errores["cui"] = error
        if not perfil.acta_aceptada:
            errores["acta_aceptada"] = "El solicitante debe firmar el acta de responsabilidad."
        return errores

    def _crear_perfil(self, cuenta, datos, fecha):
        perfil = PerfilSolicitante(
            cuenta=cuenta,
            tipo=datos.tipo,
            cui=(datos.cui or "").strip(),
            habilitado_institucional=bool(datos.habilitado_institucional),
            etiqueta=EtiquetaEstado.NUEVO,
        )
        perfil.firmar_acta(VERSION_ACTA, fecha)
        return self._perfiles.guardar(perfil)

    def completar_perfil(self, cuenta_id, datos, actor_id):
        """Crea el perfil de solicitante de una cuenta que no lo tenía (y le da el rol)."""
        cuenta = self._cuenta(cuenta_id)
        if self._perfiles.de_cuenta(cuenta.pk) is not None:
            raise OperacionNoPermitida("La cuenta ya tiene perfil de solicitante.")
        errores = self._validar_perfil(datos)
        if errores:
            raise DatosInvalidos(errores)
        with self._transaccion():
            if cuenta.asignar_rol(RolSistema.SOLICITANTE):
                self._cuentas.guardar(cuenta)
            perfil = self._crear_perfil(cuenta, datos, timezone.localdate())
            self._auditar(actor_id, cuenta.pk, "Perfil de solicitante creado y acta firmada.")
        return perfil

    # ------------------------------------------------------------------ #
    # RF-B5: roles
    # ------------------------------------------------------------------ #
    def asignar_rol(self, cuenta_id, rol, actor_id):
        """Asigna un rol a la cuenta. Devuelve False si ya lo tenía.

        Lanza CuentaNoEncontrada o RolInvalido. Deja constancia en auditoría (RF-J2).
        """
        cuenta = self._cuenta(cuenta_id)
        if not cuenta.asignar_rol(rol):
            return False
        cuenta.sincronizar_acceso_panel()
        self._cuentas.guardar(cuenta)
        self._auditar(actor_id, cuenta.pk, f"Rol asignado: {RolSistema(rol).label}")
        return True

    def quitar_rol(self, cuenta_id, rol, actor_id):
        """Quita un rol. Devuelve False si no lo tenía.

        Reglas: nadie se quita a sí mismo el rol de Administrador y el sistema
        nunca se queda sin un administrador activo.
        """
        cuenta = self._cuenta(cuenta_id)
        if rol == RolSistema.ADMINISTRADOR and cuenta.tiene_rol(rol):
            if self._mismo(cuenta.pk, actor_id):
                raise OperacionNoPermitida("No puedes quitarte tu propio rol de Administrador.")
            self._exigir_otro_administrador(cuenta)
        if not cuenta.quitar_rol(rol):
            return False
        cuenta.sincronizar_acceso_panel()
        self._cuentas.guardar(cuenta)
        self._auditar(actor_id, cuenta.pk, f"Rol quitado: {RolSistema(rol).label}")
        return True

    def _exigir_otro_administrador(self, cuenta):
        if cuenta.is_active and self._cuentas.contar_activas_con_rol(RolSistema.ADMINISTRADOR) <= 1:
            raise OperacionNoPermitida("Es el único administrador activo: el sistema no puede quedarse sin uno.")

    # ------------------------------------------------------------------ #
    # Gestión de cuentas: activar / desactivar
    # ------------------------------------------------------------------ #
    def desactivar_cuenta(self, cuenta_id, actor_id, motivo):
        """Desactiva (no borra) la cuenta. Exige motivo (RF-J1)."""
        if not (motivo or "").strip():
            raise MotivoRequerido("Indica el motivo para desactivar la cuenta.")
        cuenta = self._cuenta(cuenta_id)
        if self._mismo(cuenta.pk, actor_id):
            raise OperacionNoPermitida("No puedes desactivar tu propia cuenta.")
        if cuenta.tiene_rol(RolSistema.ADMINISTRADOR):
            self._exigir_otro_administrador(cuenta)
        if not cuenta.desactivar():
            return False
        self._cuentas.guardar(cuenta)
        self._auditar(actor_id, cuenta.pk, f"Cuenta desactivada. Motivo: {motivo.strip()}")
        return True

    def activar_cuenta(self, cuenta_id, actor_id):
        cuenta = self._cuenta(cuenta_id)
        if not cuenta.activar():
            return False
        self._cuentas.guardar(cuenta)
        self._auditar(actor_id, cuenta.pk, "Cuenta activada.")
        return True

    def cambiar_habilitacion_institucional(self, cuenta_id, habilitado, actor_id, motivo=""):
        """RF-B3: el administrador confirma o retira la condición institucional."""
        if not habilitado and not (motivo or "").strip():
            raise MotivoRequerido("Indica el motivo para retirar la habilitación institucional.")
        perfil = self._perfil(cuenta_id)
        if not perfil.cambiar_habilitacion_institucional(habilitado):
            return False
        self._perfiles.guardar(perfil)
        texto = "Habilitación institucional confirmada." if habilitado else (
            f"Habilitación institucional retirada. Motivo: {motivo.strip()}")
        self._auditar(actor_id, perfil.cuenta_id, texto)
        return True

    def actualizar_contacto(self, cuenta_id, celular, direccion):
        """El propio usuario corrige su celular y dirección (Mi perfil)."""
        cuenta = self._cuenta(cuenta_id)
        error = error_de(validar_celular, celular.strip()) if celular else None
        if error:
            raise DatosInvalidos({"celular": error})
        cuenta.actualizar_contacto(celular, direccion)
        self._cuentas.guardar(cuenta)
        return cuenta

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #
    def listar_cuentas(self, q="", rol="", estado=""):
        return self._cuentas.listar(q, rol=rol, estado=estado)

    def obtener_cuenta(self, cuenta_id):
        return self._cuenta(cuenta_id)

    def perfil_de(self, cuenta_id):
        return self._perfiles.de_cuenta(cuenta_id)

    def tipo_usuario_de(self, cuenta_id):
        """Tipo de usuario del solicitante (ALUMNO/DOCENTE/ADMINISTRATIVO), o None.

        Lo usan Políticas y Reservas para elegir la política que aplica.
        """
        perfil = self._perfiles.de_cuenta(cuenta_id)
        return perfil.tipo if perfil else None

    # ------------------------------------------------------------------ #
    # RF-B6: etiquetas automáticas
    # ------------------------------------------------------------------ #
    def actualizar_etiqueta(self, cuenta_id):
        """Recalcula y guarda la etiqueta del solicitante. Devuelve la etiqueta o None.

        BANEADO/SANCIONADO salen de Sanciones (`tiene_sancion_activa` y
        `sancion_mas_grave`); FRECUENTE sale del historial de préstamos devueltos
        a tiempo. Si la etiqueta cambia, queda en auditoría.
        """
        perfil = self._perfiles.de_cuenta(cuenta_id)
        if perfil is None:
            return None
        if self._sanciones is None and self._historial is None:
            return perfil.etiqueta  # sin fuentes no hay con qué recalcular: se respeta la guardada
        cuenta_pk = perfil.cuenta_id
        activa = bool(self._sanciones and self._sanciones.tiene_sancion_activa(cuenta_pk))
        mas_grave = self._sanciones.sancion_mas_grave(cuenta_pk) if activa else None
        a_tiempo = self._historial.devueltos_a_tiempo(cuenta_pk) if self._historial else 0

        nueva = calcular_etiqueta(activa, mas_grave, a_tiempo, self._umbral_frecuente)
        anterior = perfil.etiqueta
        if perfil.cambiar_etiqueta(nueva):
            self._perfiles.guardar(perfil)
            self._auditar(ACTOR_SISTEMA, cuenta_pk,
                          f"Etiqueta: {EtiquetaEstado(anterior).label} → {EtiquetaEstado(nueva).label} (automática)")
        return perfil.etiqueta

    def actualizar_todas_las_etiquetas(self):
        """Recalcula todas; devuelve cuántas cambiaron (comando actualizar_etiquetas)."""
        cambios = 0
        for perfil in self._perfiles.todos():
            anterior = perfil.etiqueta
            if self.actualizar_etiqueta(perfil.cuenta_id) != anterior:
                cambios += 1
        return cambios

    # ------------------------------------------------------------------ #
    # RF-B3: ¿puede solicitar? (la usa Circulación)
    # ------------------------------------------------------------------ #
    def consultar_habilitacion(self, solicitante_id) -> ResultadoHabilitacion:
        """¿El solicitante (Cuenta.id) puede pedir préstamos según Identidad?

        Revisa: cuenta existe y activa, tiene PerfilSolicitante, habilitación
        institucional, acta firmada y etiqueta distinta de SANCIONADO/BANEADO.
        Antes de revisar, refresca la etiqueta (RF-B6) para no decidir con un
        dato viejo (ej. una sanción recién aplicada).

        Nunca lanza excepción: si algo falla, responde "no habilitado" + motivo,
        para que el Core decida sin try/except.
        """
        cuenta = self._cuentas.obtener(solicitante_id)
        if cuenta is None:
            return ResultadoHabilitacion.no(solicitante_id, "La cuenta no existe.")
        if not cuenta.is_active:
            return ResultadoHabilitacion.no(solicitante_id, "La cuenta está desactivada.")

        if self._perfiles.de_cuenta(cuenta.pk) is None:
            return ResultadoHabilitacion.no(
                solicitante_id, "La cuenta no tiene perfil de solicitante."
            )
        try:
            self.actualizar_etiqueta(cuenta.pk)
        except Exception:  # noqa: BLE001 — si Sanciones falla, se decide con la etiqueta guardada
            pass
        perfil = self._perfiles.de_cuenta(cuenta.pk)

        motivos = perfil.motivos_de_inhabilitacion()
        if motivos:
            return ResultadoHabilitacion.no(solicitante_id, *motivos)
        return ResultadoHabilitacion.si(solicitante_id)

    # ------------------------------------------------------------------ #
    # Ayudantes
    # ------------------------------------------------------------------ #
    def _cuenta(self, cuenta_id):
        cuenta = self._cuentas.obtener(cuenta_id)
        if cuenta is None:
            raise CuentaNoEncontrada("La cuenta no existe.")
        return cuenta

    def _perfil(self, cuenta_id):
        perfil = self._perfiles.de_cuenta(cuenta_id)
        if perfil is None:
            raise OperacionNoPermitida("La cuenta no tiene perfil de solicitante.")
        return perfil

    @staticmethod
    def _mismo(id_a, id_b):
        return id_b is not None and str(id_a) == str(id_b)

    def _auditar(self, actor_id, cuenta_id, motivo):
        if self._auditoria is not None:
            self._auditoria.registrar(
                actor_id or ACTOR_SISTEMA, TipoAccion.CAMBIO_ESTADO, "Cuenta", cuenta_id, motivo,
            )
