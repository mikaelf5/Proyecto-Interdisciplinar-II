"""Pruebas del DOMINIO: reglas puras, sin base de datos."""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.common.choices import EtiquetaEstado, RolSistema
from apps.identidad.dominio.etiquetas import calcular_etiqueta
from apps.identidad.dominio.excepciones import ActaYaFirmada, RolInvalido
from apps.identidad.dominio.validadores import (
    validar_celular,
    validar_correo_institucional,
    validar_cui,
    validar_dni,
)

from .falsos import nueva_cuenta, perfil_ok


class EtiquetasTests(SimpleTestCase):
    """RF-B6: prioridad BANEADO > SANCIONADO > FRECUENTE > NUEVO."""

    def test_sin_historial_es_nuevo(self):
        self.assertEqual(calcular_etiqueta(False, None, 0, 5), EtiquetaEstado.NUEVO)

    def test_frecuente_desde_el_umbral(self):
        self.assertEqual(calcular_etiqueta(False, None, 4, 5), EtiquetaEstado.NUEVO)
        self.assertEqual(calcular_etiqueta(False, None, 5, 5), EtiquetaEstado.FRECUENTE)
        self.assertEqual(calcular_etiqueta(False, None, 9, 5), EtiquetaEstado.FRECUENTE)

    def test_sancion_activa_es_sancionado(self):
        for tipo in ("OBSERVACION", "SUSPENSION_TEMPORAL"):
            self.assertEqual(calcular_etiqueta(True, tipo, 0, 5), EtiquetaEstado.SANCIONADO)

    def test_baneo_es_baneado(self):
        self.assertEqual(calcular_etiqueta(True, "BANEO", 0, 5), EtiquetaEstado.BANEADO)

    def test_la_sancion_pesa_mas_que_ser_frecuente(self):
        self.assertEqual(calcular_etiqueta(True, "OBSERVACION", 20, 5), EtiquetaEstado.SANCIONADO)
        self.assertEqual(calcular_etiqueta(True, "BANEO", 20, 5), EtiquetaEstado.BANEADO)

    def test_umbral_cero_desactiva_frecuente(self):
        self.assertEqual(calcular_etiqueta(False, None, 10, 0), EtiquetaEstado.NUEVO)


class ValidadoresTests(SimpleTestCase):
    def test_dni(self):
        validar_dni("70000001")
        for malo in ("7000001", "700000011", "abcdefgh", ""):
            with self.assertRaises(ValidationError):
                validar_dni(malo)

    def test_celular(self):
        validar_celular("987654321")
        for malo in ("887654321", "98765432", "9876543210"):
            with self.assertRaises(ValidationError):
                validar_celular(malo)

    def test_correo_institucional(self):
        for bueno in ("ana@unsa.edu.pe", "Ana.Perez@UNSA.EDU.PE"):
            validar_correo_institucional(bueno)
        for malo in ("ana@gmail.com", "ana@unsa.edu.pe.com", "ana@alumnos.unsa.edu.pe",
                     "ana@unsaedu.pe", "@unsa.edu.pe", "unsa.edu.pe", ""):
            with self.assertRaises(ValidationError, msg=malo):
                validar_correo_institucional(malo)

    def test_cui(self):
        validar_cui("20230001")
        with self.assertRaises(ValidationError):
            validar_cui("2023")


class CuentaDominioTests(SimpleTestCase):
    def test_quitar_rol_idempotente(self):
        cuenta = nueva_cuenta(roles=[RolSistema.ENCARGADO, RolSistema.SOLICITANTE])
        self.assertTrue(cuenta.quitar_rol(RolSistema.ENCARGADO))
        self.assertEqual(cuenta.roles, [RolSistema.SOLICITANTE])
        self.assertFalse(cuenta.quitar_rol(RolSistema.ENCARGADO))

    def test_quitar_rol_invalido(self):
        with self.assertRaises(RolInvalido):
            nueva_cuenta().quitar_rol("JEFE")

    def test_solo_el_administrador_entra_al_panel(self):
        cuenta = nueva_cuenta(roles=[RolSistema.ENCARGADO])
        cuenta.sincronizar_acceso_panel()
        self.assertFalse(cuenta.is_staff)
        cuenta.asignar_rol(RolSistema.ADMINISTRADOR)
        cuenta.sincronizar_acceso_panel()
        self.assertTrue(cuenta.is_staff)

    def test_activar_y_desactivar(self):
        cuenta = nueva_cuenta()
        self.assertTrue(cuenta.desactivar())
        self.assertFalse(cuenta.desactivar())
        self.assertTrue(cuenta.activar())
        self.assertFalse(cuenta.activar())

    def test_consentimiento(self):
        cuenta = nueva_cuenta()
        self.assertFalse(cuenta.dio_consentimiento())
        cuenta.registrar_consentimiento("v1", date(2026, 11, 2))
        self.assertTrue(cuenta.dio_consentimiento())


class PerfilDominioTests(SimpleTestCase):
    def test_acta_se_firma_una_sola_vez(self):
        perfil = perfil_ok(nueva_cuenta(), acta_version="", acta_fecha_firma=None)
        perfil.firmar_acta("v1", date(2026, 11, 2))
        self.assertEqual((perfil.acta_version, perfil.acta_fecha_firma), ("v1", date(2026, 11, 2)))
        with self.assertRaises(ActaYaFirmada):
            perfil.firmar_acta("v2", date(2026, 12, 1))

    def test_cambiar_etiqueta(self):
        perfil = perfil_ok(nueva_cuenta())
        self.assertTrue(perfil.cambiar_etiqueta(EtiquetaEstado.FRECUENTE))
        self.assertFalse(perfil.cambiar_etiqueta(EtiquetaEstado.FRECUENTE))
        with self.assertRaises(ValueError):
            perfil.cambiar_etiqueta("VIP")
