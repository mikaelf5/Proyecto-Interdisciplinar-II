"""Tests UNITARIOS del servicio de aplicación.

Usan repositorios y hasher falsos (en memoria): no tocan la base de datos.
Esto es lo que gana la arquitectura de 4 capas: la lógica se prueba sola.
"""
import uuid

from django.test import SimpleTestCase

from apps.common.choices import EtiquetaEstado, RolSistema
from apps.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    CuentaInactiva,
    CuentaNoEncontrada,
    RolInvalido,
)

from .falsos import AuditoriaFalsa, nueva_cuenta, perfil_ok, servicio


class IniciarSesionTests(SimpleTestCase):
    def test_credenciales_correctas_devuelve_la_cuenta(self):
        cuenta = nueva_cuenta()
        self.assertIs(servicio([cuenta]).iniciar_sesion("ANA@unsa.edu.pe", "secreta123"), cuenta)

    def test_password_incorrecta(self):
        with self.assertRaises(CredencialesInvalidas):
            servicio([nueva_cuenta()]).iniciar_sesion("ana@unsa.edu.pe", "otra")

    def test_correo_inexistente_da_el_mismo_error(self):
        with self.assertRaises(CredencialesInvalidas):
            servicio().iniciar_sesion("nadie@unsa.edu.pe", "x")

    def test_cuenta_inactiva(self):
        with self.assertRaises(CuentaInactiva):
            servicio([nueva_cuenta(is_active=False)]).iniciar_sesion("ana@unsa.edu.pe", "secreta123")


class AsignarRolTests(SimpleTestCase):
    def test_asigna_guarda_y_audita(self):
        cuenta, auditoria = nueva_cuenta(), AuditoriaFalsa()
        srv = servicio([cuenta], auditoria=auditoria)
        self.assertTrue(srv.asignar_rol(cuenta.pk, RolSistema.ENCARGADO, uuid.uuid4()))
        self.assertTrue(cuenta.tiene_rol(RolSistema.ENCARGADO))
        self.assertEqual(srv._cuentas.guardadas, [cuenta])
        self.assertEqual(len(auditoria.registros), 1)

    def test_rol_repetido_no_duplica_ni_audita(self):
        cuenta, auditoria = nueva_cuenta(roles=[RolSistema.ENCARGADO]), AuditoriaFalsa()
        srv = servicio([cuenta], auditoria=auditoria)
        self.assertFalse(srv.asignar_rol(cuenta.pk, RolSistema.ENCARGADO, uuid.uuid4()))
        self.assertEqual(cuenta.roles, [RolSistema.ENCARGADO])
        self.assertEqual(auditoria.registros, [])

    def test_rol_invalido(self):
        cuenta = nueva_cuenta()
        with self.assertRaises(RolInvalido):
            servicio([cuenta]).asignar_rol(cuenta.pk, "JEFE", uuid.uuid4())

    def test_cuenta_inexistente(self):
        with self.assertRaises(CuentaNoEncontrada):
            servicio().asignar_rol(uuid.uuid4(), RolSistema.ENCARGADO, uuid.uuid4())


class ConsultarHabilitacionTests(SimpleTestCase):
    def test_habilitado(self):
        cuenta = nueva_cuenta()
        resultado = servicio([cuenta], [perfil_ok(cuenta)]).consultar_habilitacion(cuenta.pk)
        self.assertTrue(resultado)
        self.assertEqual(resultado.motivos, ())

    def test_cuenta_inexistente(self):
        resultado = servicio().consultar_habilitacion(uuid.uuid4())
        self.assertFalse(resultado)
        self.assertIn("no existe", resultado.mensaje)

    def test_cuenta_desactivada(self):
        cuenta = nueva_cuenta(is_active=False)
        self.assertFalse(servicio([cuenta], [perfil_ok(cuenta)]).consultar_habilitacion(cuenta.pk))

    def test_sin_perfil_de_solicitante(self):
        cuenta = nueva_cuenta()
        resultado = servicio([cuenta]).consultar_habilitacion(cuenta.pk)
        self.assertFalse(resultado)
        self.assertIn("perfil", resultado.mensaje)

    def test_no_habilitado_institucionalmente(self):
        cuenta = nueva_cuenta()
        perfil = perfil_ok(cuenta, habilitado_institucional=False)
        self.assertFalse(servicio([cuenta], [perfil]).consultar_habilitacion(cuenta.pk))

    def test_sin_acta_firmada(self):
        cuenta = nueva_cuenta()
        perfil = perfil_ok(cuenta, acta_fecha_firma=None)
        resultado = servicio([cuenta], [perfil]).consultar_habilitacion(cuenta.pk)
        self.assertIn("acta", resultado.mensaje)

    def test_sancionado_y_baneado(self):
        for etiqueta in (EtiquetaEstado.SANCIONADO, EtiquetaEstado.BANEADO):
            cuenta = nueva_cuenta()
            perfil = perfil_ok(cuenta, etiqueta=etiqueta)
            self.assertFalse(servicio([cuenta], [perfil]).consultar_habilitacion(cuenta.pk))

    def test_frecuente_si_puede(self):
        cuenta = nueva_cuenta()
        perfil = perfil_ok(cuenta, etiqueta=EtiquetaEstado.FRECUENTE)
        self.assertTrue(servicio([cuenta], [perfil]).consultar_habilitacion(cuenta.pk))

    def test_junta_todos_los_motivos(self):
        cuenta = nueva_cuenta()
        perfil = perfil_ok(cuenta, habilitado_institucional=False, acta_version="",
                           etiqueta=EtiquetaEstado.BANEADO)
        self.assertEqual(len(servicio([cuenta], [perfil]).consultar_habilitacion(cuenta.pk).motivos), 3)
