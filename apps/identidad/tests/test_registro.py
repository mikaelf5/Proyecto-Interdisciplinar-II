"""Registro por autoservicio + aprobación/rechazo del administrador."""
import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.common.choices import EtiquetaEstado, RolSistema, TipoUsuario
from apps.identidad.aplicacion.dtos import AprobacionRegistroDTO, SolicitudRegistroDTO
from apps.identidad.aplicacion.registro import RegistroServicioAplicacion
from apps.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    DatosInvalidos,
    MotivoRequerido,
    RegistroNoAprobado,
    SolicitudYaRevisada,
)
from apps.identidad.dominio.models import EstadoRegistro, SolicitudRegistro

from .falsos import (
    AuditoriaFalsa,
    CorreoFalso,
    CuentaRepoFalso,
    HasherFalso,
    PerfilRepoFalso,
    SolicitudRepoFalso,
    nueva_cuenta,
    servicio,
)

ADMIN = uuid.uuid4()


def pdf(nombre="carne.pdf", tamanio=100):
    return SimpleUploadedFile(nombre, b"%PDF" + b"x" * tamanio, content_type="application/pdf")


def dto(**extra):
    datos = dict(
        nombres="Rosa Mamani", dni="72345678", correo="RMamani@unsa.edu.pe",
        password="Clave-Segura-1", celular="987654321", direccion="Calle Mercaderes 100",
        tipo=TipoUsuario.ALUMNO, cui="20231111",
        tipo_documento="CARNE_UNIVERSITARIO", documento=pdf(),
        acta_aceptada=True, consentimiento_aceptado=True,
    )
    datos.update(extra)
    return SolicitudRegistroDTO(**datos)


class Entorno:
    def __init__(self, cuentas=(), correo_falla=False):
        self.cuentas = CuentaRepoFalso(*cuentas)
        self.perfiles = PerfilRepoFalso()
        self.solicitudes = SolicitudRepoFalso()
        self.correo = CorreoFalso(falla=correo_falla)
        self.auditoria = AuditoriaFalsa()
        self.servicio = RegistroServicioAplicacion(
            self.solicitudes, self.cuentas, self.perfiles, HasherFalso(),
            correo=self.correo, auditoria=self.auditoria,
        )


class SolicitarTests(SimpleTestCase):
    def test_queda_pendiente_sin_crear_cuenta_y_con_password_hasheada(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        self.assertEqual(s.estado, EstadoRegistro.PENDIENTE)
        self.assertEqual(s.correo, "rmamani@unsa.edu.pe")
        self.assertEqual(s.password_hash, "hash::Clave-Segura-1")
        self.assertEqual(s.acta_version, "v1")
        self.assertEqual(e.cuentas.cuentas, {})

    def test_exige_correo_institucional(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            Entorno().servicio.solicitar(dto(correo="rosa@gmail.com"))
        self.assertIn("correo", ctx.exception.errores)

    def test_exige_documento_valido(self):
        e = Entorno()
        for documento in (None, pdf("foto.exe"), pdf(tamanio=6 * 1024 * 1024)):
            with self.subTest(documento=documento):
                with self.assertRaises(DatosInvalidos) as ctx:
                    e.servicio.solicitar(dto(documento=documento))
                self.assertIn("documento", ctx.exception.errores)

    def test_alumno_sin_cui_y_sin_acta_ni_consentimiento(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            Entorno().servicio.solicitar(dto(cui="", acta_aceptada=False,
                                             consentimiento_aceptado=False))
        self.assertTrue({"cui", "acta_aceptada", "consentimiento_aceptado"}
                        <= set(ctx.exception.errores))

    def test_no_permite_duplicar_cuenta_ni_solicitud_pendiente(self):
        e = Entorno(cuentas=[nueva_cuenta(correo="rmamani@unsa.edu.pe", dni="72345678")])
        with self.assertRaises(DatosInvalidos) as ctx:
            e.servicio.solicitar(dto())
        self.assertEqual({"correo", "dni"}, set(ctx.exception.errores) & {"correo", "dni"})

        e = Entorno()
        e.servicio.solicitar(dto())
        with self.assertRaises(DatosInvalidos) as ctx:
            e.servicio.solicitar(dto(documento=pdf()))
        self.assertIn("ya hay una solicitud", ctx.exception.errores["correo"].lower())


class AprobarRechazarTests(SimpleTestCase):
    def test_aprobar_crea_cuenta_con_rol_perfil_habilitado_y_avisa(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        cuenta = e.servicio.aprobar(s.pk, AprobacionRegistroDTO(roles=[RolSistema.SOLICITANTE]), ADMIN)

        self.assertEqual(cuenta.roles, [RolSistema.SOLICITANTE])
        self.assertEqual(cuenta.password, "hash::Clave-Segura-1")   # la que ella eligió
        self.assertTrue(cuenta.dio_consentimiento())
        perfil = e.perfiles.de_cuenta(cuenta.pk)
        self.assertTrue(perfil.habilitado_institucional)
        self.assertTrue(perfil.acta_firmada())
        self.assertEqual(perfil.etiqueta, EtiquetaEstado.NUEVO)
        self.assertEqual(s.estado, EstadoRegistro.APROBADA)
        self.assertEqual(s.revisado_por_id, ADMIN)
        self.assertEqual(e.correo.enviados, [("aprobada", "rmamani@unsa.edu.pe", ("SOLICITANTE",))])
        self.assertEqual(len(e.auditoria.registros), 1)

    def test_aprobar_como_personal_sin_perfil(self):
        e = Entorno()
        s = e.servicio.solicitar(dto(tipo=TipoUsuario.DOCENTE, cui=""))
        cuenta = e.servicio.aprobar(s.pk, AprobacionRegistroDTO(roles=[RolSistema.ENCARGADO]), ADMIN)
        self.assertEqual(cuenta.roles, [RolSistema.ENCARGADO])
        self.assertIsNone(e.perfiles.de_cuenta(cuenta.pk))

    def test_admin_puede_corregir_el_tipo_declarado(self):
        e = Entorno()
        s = e.servicio.solicitar(dto(tipo=TipoUsuario.DOCENTE))
        cuenta = e.servicio.aprobar(s.pk, AprobacionRegistroDTO(
            roles=[RolSistema.SOLICITANTE], tipo=TipoUsuario.ALUMNO), ADMIN)
        self.assertEqual(e.perfiles.de_cuenta(cuenta.pk).tipo, TipoUsuario.ALUMNO)

    def test_aprobar_sin_roles_falla(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        with self.assertRaises(DatosInvalidos):
            e.servicio.aprobar(s.pk, AprobacionRegistroDTO(roles=[]), ADMIN)
        self.assertTrue(s.esta_pendiente())

    def test_no_se_revisa_dos_veces(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        e.servicio.rechazar(s.pk, "Carné vencido.", ADMIN)
        with self.assertRaises(SolicitudYaRevisada):
            e.servicio.aprobar(s.pk, AprobacionRegistroDTO(roles=[RolSistema.SOLICITANTE]), ADMIN)

    def test_rechazar_exige_motivo_y_avisa(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        with self.assertRaises(MotivoRequerido):
            e.servicio.rechazar(s.pk, "  ", ADMIN)
        e.servicio.rechazar(s.pk, "Carné vencido.", ADMIN)
        self.assertEqual(s.estado, EstadoRegistro.RECHAZADA)
        self.assertEqual(e.correo.enviados, [("rechazada", "rmamani@unsa.edu.pe", "Carné vencido.")])

    def test_tras_rechazo_puede_volver_a_solicitar(self):
        e = Entorno()
        s = e.servicio.solicitar(dto())
        e.servicio.rechazar(s.pk, "Carné vencido.", ADMIN)
        self.assertTrue(e.servicio.solicitar(dto(documento=pdf())).esta_pendiente())

    def test_si_falla_el_correo_la_aprobacion_igual_queda(self):
        e = Entorno(correo_falla=True)
        s = e.servicio.solicitar(dto())
        with self.assertLogs("apps.identidad.aplicacion.registro", "ERROR"):
            e.servicio.aprobar(s.pk, AprobacionRegistroDTO(roles=[RolSistema.SOLICITANTE]), ADMIN)
        self.assertEqual(s.estado, EstadoRegistro.APROBADA)


class LoginConRegistroPendienteTests(SimpleTestCase):
    def _servicio_con(self, solicitud):
        svc = servicio()
        svc._solicitudes = SolicitudRepoFalso(solicitud)
        return svc

    def _solicitud(self, **extra):
        return SolicitudRegistro(id=uuid.uuid4(), correo="rosa@unsa.edu.pe",
                                 password_hash="hash::Clave-Segura-1", **extra)

    def test_pendiente_avisa_que_esta_en_revision(self):
        with self.assertRaisesMessage(RegistroNoAprobado, "en revisión"):
            self._servicio_con(self._solicitud()).iniciar_sesion("rosa@unsa.edu.pe", "Clave-Segura-1")

    def test_rechazada_muestra_motivo(self):
        s = self._solicitud(estado=EstadoRegistro.RECHAZADA, motivo_rechazo="Carné vencido.")
        with self.assertRaisesMessage(RegistroNoAprobado, "Carné vencido."):
            self._servicio_con(s).iniciar_sesion("rosa@unsa.edu.pe", "Clave-Segura-1")

    def test_con_password_incorrecta_no_revela_nada(self):
        with self.assertRaises(CredencialesInvalidas):
            self._servicio_con(self._solicitud()).iniciar_sesion("rosa@unsa.edu.pe", "otra")


# ---------------------------------------------------------------------- #
# Integración: pantallas + BD + correo
# ---------------------------------------------------------------------- #
import shutil  # noqa: E402
import tempfile  # noqa: E402

MEDIA_PRUEBA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_PRUEBA,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FlujoRegistroPantallasTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_PRUEBA, ignore_errors=True)

    def setUp(self):
        Cuenta = get_user_model()
        self.admin = Cuenta.objects.create_user("admin@unsa.edu.pe", "Admin", "70000009",
                                                "secreta123", roles=[RolSistema.ADMINISTRADOR])

    def _enviar(self, **extra):
        datos = {
            "nombres": "Rosa Mamani", "dni": "72345678", "tipo": "ALUMNO", "cui": "20231111",
            "celular": "987654321", "direccion": "Calle Mercaderes 100",
            "tipo_documento": "CARNE_UNIVERSITARIO", "documento": pdf(),
            "correo": "rosa@unsa.edu.pe", "password1": "Clave-Segura-1",
            "password2": "Clave-Segura-1", "acta_aceptada": "on", "consentimiento_aceptado": "on",
        }
        datos.update(extra)
        return self.client.post(reverse("identidad:registro"), datos)

    def _login(self, correo, password):
        return self.client.post(reverse("identidad:login"), {"correo": correo, "password": password})

    def test_flujo_completo_aprobacion(self):
        respuesta = self._enviar()
        self.assertRedirects(respuesta, reverse("identidad:registro_enviado"))
        solicitud = SolicitudRegistro.objects.get()

        # Aún no puede entrar
        self.assertContains(self._login("rosa@unsa.edu.pe", "Clave-Segura-1"), "en revisión")

        # El admin ve el documento y aprueba
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(
            reverse("identidad:documento_solicitud", args=[solicitud.pk])).status_code, 200)
        self.client.post(reverse("identidad:aprobar_solicitud", args=[solicitud.pk]),
                         {"roles": ["SOLICITANTE"], "tipo": "ALUMNO"})
        self.client.logout()

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoRegistro.APROBADA)
        self.assertTrue(solicitud.cuenta.perfil.habilitado_institucional)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("aprobada", mail.outbox[0].subject)
        self.assertIn("/identidad/login/", mail.outbox[0].body)

        # Ya entra con la contraseña que eligió
        self.assertRedirects(self._login("rosa@unsa.edu.pe", "Clave-Segura-1"), reverse("home"),
                             fetch_redirect_response=False)

    def test_rechazo_envia_correo_con_motivo(self):
        self._enviar()
        solicitud = SolicitudRegistro.objects.get()
        self.client.force_login(self.admin)
        self.client.post(reverse("identidad:rechazar_solicitud", args=[solicitud.pk]),
                         {"motivo": "El carné está vencido."})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoRegistro.RECHAZADA)
        self.assertIn("El carné está vencido.", mail.outbox[0].body)
        self.assertFalse(get_user_model().objects.filter(correo="rosa@unsa.edu.pe").exists())

    def test_correo_no_institucional_se_rechaza_en_el_formulario(self):
        respuesta = self._enviar(correo="rosa@gmail.com")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "@unsa.edu.pe")
        self.assertFalse(SolicitudRegistro.objects.exists())

    def test_solo_el_admin_ve_solicitudes_y_documentos(self):
        self._enviar()
        solicitud = SolicitudRegistro.objects.get()
        url = reverse("identidad:documento_solicitud", args=[solicitud.pk])
        self.assertEqual(self.client.get(url).status_code, 302)          # sin sesión -> login
        otro = get_user_model().objects.create_user("x@unsa.edu.pe", "X", "70000008", "secreta123",
                                                    roles=[RolSistema.SOLICITANTE])
        self.client.force_login(otro)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("identidad:solicitudes")).status_code, 403)
