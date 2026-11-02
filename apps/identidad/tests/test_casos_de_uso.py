"""Pruebas UNITARIAS de los casos de uso nuevos (repos, hasher y puertos falsos: sin BD)."""
import uuid

from django.test import SimpleTestCase

from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.identidad.aplicacion.dtos import PerfilSolicitanteDTO, RegistroCuentaDTO
from apps.identidad.dominio.excepciones import (
    CuentaNoEncontrada,
    DatosInvalidos,
    MotivoRequerido,
    OperacionNoPermitida,
)

from .falsos import (
    AuditoriaFalsa,
    HistorialFalso,
    SancionesFalsas,
    nueva_cuenta,
    perfil_ok,
    servicio,
)


def dto_solicitante(**extra):
    datos = dict(
        nombres="Luis Quispe", dni="71234567", correo="LQuispe@unsa.edu.pe",
        password="Clave-Segura-1", celular="987654321", direccion="Av. Independencia 123",
        roles=[RolSistema.SOLICITANTE], consentimiento_aceptado=True,
        perfil=PerfilSolicitanteDTO(tipo=TipoUsuario.ALUMNO, cui="20231234",
                                    habilitado_institucional=True, acta_aceptada=True),
    )
    datos.update(extra)
    return RegistroCuentaDTO(**datos)


class RegistrarCuentaTests(SimpleTestCase):
    """RF-B1, RF-B2, RNF-2."""

    def test_registra_cuenta_perfil_acta_y_consentimiento(self):
        auditoria = AuditoriaFalsa()
        srv = servicio(auditoria=auditoria)
        cuenta = srv.registrar_cuenta(dto_solicitante(), uuid.uuid4())

        self.assertEqual(cuenta.correo, "lquispe@unsa.edu.pe")  # se normaliza
        self.assertEqual(cuenta.password, "hash::Clave-Segura-1")  # nunca en texto plano
        self.assertEqual(cuenta.roles, [RolSistema.SOLICITANTE])
        self.assertEqual(cuenta.consentimiento_version, "v1")
        self.assertIsNotNone(cuenta.consentimiento_fecha)

        perfil = srv.perfil_de(cuenta.pk)
        self.assertEqual((perfil.tipo, perfil.cui), (TipoUsuario.ALUMNO, "20231234"))
        self.assertEqual(perfil.acta_version, "v1")
        self.assertIsNotNone(perfil.acta_fecha_firma)
        self.assertEqual(perfil.etiqueta, EtiquetaEstado.NUEVO)
        self.assertEqual(len(auditoria.registros), 1)

    def test_personal_sin_perfil(self):
        srv = servicio()
        cuenta = srv.registrar_cuenta(dto_solicitante(roles=[RolSistema.ENCARGADO], perfil=None), uuid.uuid4())
        self.assertIsNone(srv.perfil_de(cuenta.pk))
        self.assertFalse(cuenta.is_staff)

    def test_administrador_queda_con_acceso_al_panel(self):
        cuenta = servicio().registrar_cuenta(
            dto_solicitante(roles=[RolSistema.ADMINISTRADOR], perfil=None), uuid.uuid4())
        self.assertTrue(cuenta.is_staff)

    def test_sin_consentimiento_no_se_registra(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            servicio().registrar_cuenta(dto_solicitante(consentimiento_aceptado=False), uuid.uuid4())
        self.assertIn("consentimiento_aceptado", ctx.exception.errores)

    def test_solicitante_sin_acta_no_se_registra(self):
        perfil = PerfilSolicitanteDTO(tipo=TipoUsuario.DOCENTE, acta_aceptada=False)
        with self.assertRaises(DatosInvalidos) as ctx:
            servicio().registrar_cuenta(dto_solicitante(perfil=perfil), uuid.uuid4())
        self.assertIn("acta_aceptada", ctx.exception.errores)

    def test_alumno_necesita_cui_docente_no(self):
        sin_cui = PerfilSolicitanteDTO(tipo=TipoUsuario.ALUMNO, acta_aceptada=True)
        with self.assertRaises(DatosInvalidos) as ctx:
            servicio().registrar_cuenta(dto_solicitante(perfil=sin_cui), uuid.uuid4())
        self.assertIn("cui", ctx.exception.errores)
        docente = PerfilSolicitanteDTO(tipo=TipoUsuario.DOCENTE, acta_aceptada=True)
        servicio().registrar_cuenta(dto_solicitante(perfil=docente), uuid.uuid4())

    def test_correo_y_dni_repetidos(self):
        existente = nueva_cuenta(correo="lquispe@unsa.edu.pe", dni="71234567")
        with self.assertRaises(DatosInvalidos) as ctx:
            servicio([existente]).registrar_cuenta(dto_solicitante(), uuid.uuid4())
        self.assertEqual(set(ctx.exception.errores), {"correo", "dni"})

    def test_correo_debe_ser_institucional(self):
        for correo in ("luis@gmail.com", "luis@unsa.edu.pe.com", "@unsa.edu.pe", "luis"):
            with self.assertRaises(DatosInvalidos, msg=correo) as ctx:
                servicio().registrar_cuenta(dto_solicitante(correo=correo), uuid.uuid4())
            self.assertIn("@unsa.edu.pe", ctx.exception.errores["correo"])

    def test_junta_todos_los_errores(self):
        dto = dto_solicitante(nombres=" ", dni="123", celular="12345", roles=[],
                              consentimiento_aceptado=False)
        with self.assertRaises(DatosInvalidos) as ctx:
            servicio().registrar_cuenta(dto, uuid.uuid4())
        self.assertEqual(set(ctx.exception.errores),
                         {"nombres", "dni", "celular", "roles", "consentimiento_aceptado"})


class GestionCuentasTests(SimpleTestCase):
    def setUp(self):
        self.admin = nueva_cuenta("admin@unsa.edu.pe", dni="70000009", roles=[RolSistema.ADMINISTRADOR])
        self.otro_admin = nueva_cuenta("admin2@unsa.edu.pe", dni="70000008", roles=[RolSistema.ADMINISTRADOR])
        self.ana = nueva_cuenta(roles=[RolSistema.SOLICITANTE, RolSistema.ENCARGADO])
        self.auditoria = AuditoriaFalsa()

    def srv(self, *cuentas):
        return servicio(cuentas or [self.admin, self.ana], auditoria=self.auditoria)

    def test_quitar_rol_guarda_y_audita(self):
        srv = self.srv()
        self.assertTrue(srv.quitar_rol(self.ana.pk, RolSistema.ENCARGADO, self.admin.pk))
        self.assertEqual(self.ana.roles, [RolSistema.SOLICITANTE])
        self.assertEqual(len(self.auditoria.registros), 1)
        self.assertFalse(srv.quitar_rol(self.ana.pk, RolSistema.ENCARGADO, self.admin.pk))

    def test_no_te_quitas_tu_propio_rol_de_admin(self):
        with self.assertRaises(OperacionNoPermitida):
            self.srv(self.admin, self.otro_admin).quitar_rol(
                self.admin.pk, RolSistema.ADMINISTRADOR, self.admin.pk)

    def test_no_se_queda_sin_administradores(self):
        with self.assertRaises(OperacionNoPermitida):
            self.srv(self.admin).quitar_rol(self.admin.pk, RolSistema.ADMINISTRADOR, uuid.uuid4())

    def test_con_otro_admin_si_se_puede_quitar(self):
        srv = self.srv(self.admin, self.otro_admin)
        self.assertTrue(srv.quitar_rol(self.otro_admin.pk, RolSistema.ADMINISTRADOR, self.admin.pk))
        self.assertFalse(self.otro_admin.is_staff)

    def test_desactivar_exige_motivo(self):
        with self.assertRaises(MotivoRequerido):
            self.srv().desactivar_cuenta(self.ana.pk, self.admin.pk, "  ")

    def test_desactivar_y_activar(self):
        srv = self.srv()
        self.assertTrue(srv.desactivar_cuenta(self.ana.pk, self.admin.pk, "Egresó"))
        self.assertFalse(self.ana.is_active)
        self.assertIn("Egresó", self.auditoria.registros[-1][-1])
        self.assertFalse(srv.desactivar_cuenta(self.ana.pk, self.admin.pk, "otra vez"))
        self.assertTrue(srv.activar_cuenta(self.ana.pk, self.admin.pk))
        self.assertTrue(self.ana.is_active)

    def test_no_te_desactivas_a_ti_mismo(self):
        with self.assertRaises(OperacionNoPermitida):
            self.srv().desactivar_cuenta(self.admin.pk, self.admin.pk, "prueba")

    def test_no_se_desactiva_al_ultimo_admin(self):
        with self.assertRaises(OperacionNoPermitida):
            self.srv(self.admin, self.ana).desactivar_cuenta(self.admin.pk, self.ana.pk, "x")

    def test_cuenta_inexistente(self):
        with self.assertRaises(CuentaNoEncontrada):
            self.srv().activar_cuenta(uuid.uuid4(), self.admin.pk)

    def test_retirar_habilitacion_exige_motivo(self):
        srv = servicio([self.ana], [perfil_ok(self.ana)], auditoria=self.auditoria)
        with self.assertRaises(MotivoRequerido):
            srv.cambiar_habilitacion_institucional(self.ana.pk, False, self.admin.pk)
        self.assertTrue(srv.cambiar_habilitacion_institucional(self.ana.pk, False, self.admin.pk, "Sin matrícula"))
        self.assertFalse(srv.consultar_habilitacion(self.ana.pk))

    def test_completar_perfil(self):
        cuenta = nueva_cuenta(roles=[RolSistema.ENCARGADO])
        srv = servicio([cuenta])
        srv.completar_perfil(cuenta.pk, PerfilSolicitanteDTO(
            tipo=TipoUsuario.ADMINISTRATIVO, acta_aceptada=True, habilitado_institucional=True), self.admin.pk)
        self.assertTrue(cuenta.tiene_rol(RolSistema.SOLICITANTE))
        self.assertTrue(srv.consultar_habilitacion(cuenta.pk))
        with self.assertRaises(OperacionNoPermitida):
            srv.completar_perfil(cuenta.pk, PerfilSolicitanteDTO(tipo=TipoUsuario.ALUMNO), self.admin.pk)

    def test_actualizar_contacto_valida_celular(self):
        srv = self.srv()
        with self.assertRaises(DatosInvalidos):
            srv.actualizar_contacto(self.ana.pk, "123", "")
        srv.actualizar_contacto(self.ana.pk, "912345678", "Calle 1")
        self.assertEqual((self.ana.celular, self.ana.direccion), ("912345678", "Calle 1"))


class TipoUsuarioDeTests(SimpleTestCase):
    def test_devuelve_el_tipo_del_perfil(self):
        cuenta = nueva_cuenta()
        srv = servicio([cuenta], [perfil_ok(cuenta, tipo=TipoUsuario.DOCENTE)])
        self.assertEqual(srv.tipo_usuario_de(cuenta.pk), TipoUsuario.DOCENTE)

    def test_sin_perfil_devuelve_none(self):
        cuenta = nueva_cuenta()
        self.assertIsNone(servicio([cuenta]).tipo_usuario_de(cuenta.pk))
        self.assertIsNone(servicio().tipo_usuario_de(uuid.uuid4()))


class EtiquetasAutomaticasTests(SimpleTestCase):
    """RF-B6 con los puertos falsos de Sanciones y del historial de préstamos."""

    def setUp(self):
        self.cuenta = nueva_cuenta()
        self.perfil = perfil_ok(self.cuenta)
        self.auditoria = AuditoriaFalsa()

    def srv(self, sanciones=None, a_tiempo=0, umbral=3):
        return servicio([self.cuenta], [self.perfil], auditoria=self.auditoria,
                        sanciones=SancionesFalsas(sanciones),
                        historial=HistorialFalso({self.cuenta.pk: a_tiempo}), umbral=umbral)

    def test_frecuente_despues_de_n_devoluciones_a_tiempo(self):
        self.assertEqual(self.srv(a_tiempo=2).actualizar_etiqueta(self.cuenta.pk), EtiquetaEstado.NUEVO)
        self.assertEqual(self.srv(a_tiempo=3).actualizar_etiqueta(self.cuenta.pk), EtiquetaEstado.FRECUENTE)
        self.assertEqual(self.perfil.etiqueta, EtiquetaEstado.FRECUENTE)
        self.assertEqual(len(self.auditoria.registros), 1)  # se audita solo el cambio

    def test_sancionado_y_baneado_segun_sanciones(self):
        srv = self.srv({self.cuenta.pk: "SUSPENSION_TEMPORAL"}, a_tiempo=10)
        self.assertEqual(srv.actualizar_etiqueta(self.cuenta.pk), EtiquetaEstado.SANCIONADO)
        srv = self.srv({self.cuenta.pk: "BANEO"})
        self.assertEqual(srv.actualizar_etiqueta(self.cuenta.pk), EtiquetaEstado.BANEADO)

    def test_al_levantar_la_sancion_vuelve(self):
        self.perfil.etiqueta = EtiquetaEstado.SANCIONADO
        self.assertEqual(self.srv(a_tiempo=5).actualizar_etiqueta(self.cuenta.pk), EtiquetaEstado.FRECUENTE)

    def test_sin_cambio_no_audita(self):
        self.srv().actualizar_etiqueta(self.cuenta.pk)
        self.assertEqual(self.auditoria.registros, [])

    def test_consultar_habilitacion_usa_la_etiqueta_fresca(self):
        srv = self.srv({self.cuenta.pk: "BANEO"})
        resultado = srv.consultar_habilitacion(self.cuenta.pk)
        self.assertFalse(resultado)
        self.assertIn("baneado", resultado.mensaje)

    def test_si_sanciones_falla_no_revienta(self):
        class SancionesRotas(SancionesFalsas):
            def tiene_sancion_activa(self, cuenta_id):
                raise RuntimeError("BD caída")

        srv = servicio([self.cuenta], [self.perfil], sanciones=SancionesRotas())
        self.assertTrue(srv.consultar_habilitacion(self.cuenta.pk))

    def test_sin_perfil_devuelve_none(self):
        otra = nueva_cuenta("x@unsa.edu.pe", dni="70000002")
        self.assertIsNone(servicio([otra], sanciones=SancionesFalsas()).actualizar_etiqueta(otra.pk))

    def test_actualizar_todas(self):
        self.assertEqual(self.srv(a_tiempo=3).actualizar_todas_las_etiquetas(), 1)
