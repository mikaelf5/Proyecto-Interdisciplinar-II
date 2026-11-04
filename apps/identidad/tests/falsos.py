"""Dobles de prueba (en memoria) para probar los casos de uso SIN base de datos."""
import uuid
from datetime import date

from apps.common.choices import TipoUsuario
from apps.identidad.aplicacion.servicios import CuentaServicioAplicacion
from apps.identidad.dominio.hasher import IPasswordHasher
from apps.identidad.dominio.models import Cuenta, PerfilSolicitante
from apps.identidad.dominio.puertos import IHistorialPrestamosPuerto, ISancionesPuerto
from apps.identidad.dominio.repositorio import (
    ICuentaRepositorio,
    IPerfilSolicitanteRepositorio,
)


class HasherFalso(IPasswordHasher):
    def hashear(self, password_plano):
        return f"hash::{password_plano}"

    def verificar(self, password_plano, password_hash):
        return password_hash == f"hash::{password_plano}"


class CuentaRepoFalso(ICuentaRepositorio):
    def __init__(self, *cuentas):
        self.cuentas = {c.pk: c for c in cuentas}
        self.guardadas = []

    def obtener(self, cuenta_id):
        return self.cuentas.get(cuenta_id)

    def por_correo(self, correo):
        return next((c for c in self.cuentas.values() if c.correo.lower() == correo.lower()), None)

    def existe_dni(self, dni):
        return any(c.dni == dni for c in self.cuentas.values())

    def contar_activas_con_rol(self, rol):
        return sum(1 for c in self.cuentas.values() if c.is_active and c.tiene_rol(rol))

    def guardar(self, cuenta):
        if cuenta.pk is None:
            cuenta.pk = uuid.uuid4()
        self.cuentas[cuenta.pk] = cuenta
        self.guardadas.append(cuenta)
        return cuenta

    def listar(self, q="", rol="", estado=""):
        return list(self.cuentas.values())


class PerfilRepoFalso(IPerfilSolicitanteRepositorio):
    def __init__(self, *perfiles):
        self.perfiles = {p.cuenta.pk: p for p in perfiles}
        self.guardados = []

    def de_cuenta(self, cuenta_id):
        return self.perfiles.get(cuenta_id)

    def guardar(self, perfil):
        perfil.cuenta_id = perfil.cuenta.pk  # la cuenta se "guardó" después de crear el perfil
        self.perfiles[perfil.cuenta.pk] = perfil
        self.guardados.append(perfil)
        return perfil

    def todos(self):
        return list(self.perfiles.values())


class AuditoriaFalsa:
    def __init__(self):
        self.registros = []

    def registrar(self, *args):
        self.registros.append(args)


class SancionesFalsas(ISancionesPuerto):
    """`tipos` = {cuenta_id: "BANEO" | "SUSPENSION_TEMPORAL" | "OBSERVACION"} vigentes."""

    def __init__(self, tipos=None):
        self.tipos = dict(tipos or {})

    def tiene_sancion_activa(self, cuenta_id):
        return cuenta_id in self.tipos

    def sancion_mas_grave(self, cuenta_id):
        return self.tipos.get(cuenta_id)


class HistorialFalso(IHistorialPrestamosPuerto):
    def __init__(self, a_tiempo=None):
        self.a_tiempo = dict(a_tiempo or {})

    def devueltos_a_tiempo(self, cuenta_id):
        return self.a_tiempo.get(cuenta_id, 0)


def nueva_cuenta(correo="ana@unsa.edu.pe", password="secreta123", dni="70000001", **extra):
    cuenta = Cuenta(id=uuid.uuid4(), correo=correo, nombres="Ana", dni=dni, **extra)
    cuenta.password = HasherFalso().hashear(password)
    return cuenta


def perfil_ok(cuenta, **extra):
    datos = dict(
        cuenta=cuenta, tipo=TipoUsuario.ALUMNO, cui="20230001", habilitado_institucional=True,
        acta_version="v1", acta_fecha_firma=date(2026, 10, 1),
    )
    datos.update(extra)
    return PerfilSolicitante(**datos)


def servicio(cuentas=(), perfiles=(), auditoria=None, sanciones=None, historial=None, umbral=5):
    return CuentaServicioAplicacion(
        CuentaRepoFalso(*cuentas), PerfilRepoFalso(*perfiles), HasherFalso(), auditoria,
        sanciones=sanciones, historial=historial, umbral_frecuente=umbral,
    )


# ---------- Registro por autoservicio ----------
class SolicitudRepoFalso:
    def __init__(self, *solicitudes):
        self.solicitudes = {s.pk: s for s in solicitudes}

    def obtener(self, solicitud_id):
        return self.solicitudes.get(solicitud_id)

    def hay_pendiente(self, correo="", dni=""):
        return any(s.esta_pendiente() and ((correo and s.correo.lower() == correo.lower())
                                           or (dni and s.dni == dni))
                   for s in self.solicitudes.values())

    def ultima_por_correo(self, correo):
        mismas = [s for s in self.solicitudes.values() if s.correo.lower() == correo.lower()]
        return mismas[-1] if mismas else None

    def guardar(self, solicitud):
        self.solicitudes[solicitud.pk] = solicitud
        return solicitud

    def listar(self, estado=""):
        return [s for s in self.solicitudes.values() if not estado or s.estado == estado]

    def contar_pendientes(self):
        return len(self.listar("PENDIENTE"))


class CorreoFalso:
    def __init__(self, falla=False):
        self.enviados = []
        self.falla = falla

    def avisar_aprobacion(self, solicitud, roles):
        if self.falla:
            raise ConnectionError("SMTP caído")
        self.enviados.append(("aprobada", solicitud.correo, tuple(roles)))

    def avisar_rechazo(self, solicitud):
        self.enviados.append(("rechazada", solicitud.correo, solicitud.motivo_rechazo))
