"""Tests de INTEGRACIÓN: capas reales + PostgreSQL + vistas."""
import uuid
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.common.choices import RolSistema, TipoUsuario
from apps.identidad.fabrica import cuenta_servicio
from apps.identidad.infraestructura.django_password_hasher import DjangoPasswordHasher
from apps.identidad.models import Cuenta, PerfilSolicitante


def crear_cuenta(correo="ana@unsa.edu.pe", dni="70000001", roles=None, **extra):
    return Cuenta.objects.create_user(
        correo=correo, nombres="Ana Pérez", dni=dni, password="secreta123",
        roles=roles or [], **extra,
    )


class DjangoPasswordHasherTests(TestCase):
    def test_hashea_con_sal_y_verifica(self):
        hasher = DjangoPasswordHasher()
        h1, h2 = hasher.hashear("clave"), hasher.hashear("clave")
        self.assertNotEqual(h1, "clave")
        self.assertNotEqual(h1, h2)  # sal distinta en cada hash
        self.assertTrue(hasher.verificar("clave", h1))
        self.assertFalse(hasher.verificar("otra", h1))


class ServicioConBDTests(TestCase):
    def test_consultar_habilitacion_con_bd(self):
        cuenta = crear_cuenta()
        PerfilSolicitante.objects.create(
            cuenta=cuenta, tipo=TipoUsuario.ALUMNO, habilitado_institucional=True,
            acta_version="v1", acta_fecha_firma=date.today(),
        )
        self.assertTrue(cuenta_servicio().consultar_habilitacion(cuenta.pk))

    def test_consultar_habilitacion_id_invalido_no_revienta(self):
        self.assertFalse(cuenta_servicio().consultar_habilitacion("no-es-uuid"))
        self.assertFalse(cuenta_servicio().consultar_habilitacion(uuid.uuid4()))

    def test_asignar_rol_persiste_y_queda_en_auditoria(self):
        cuenta, admin = crear_cuenta(), crear_cuenta("admin@unsa.edu.pe", "70000002")
        cuenta_servicio().asignar_rol(cuenta.pk, RolSistema.SUPERVISOR, admin.pk)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.roles, [RolSistema.SUPERVISOR])
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="Cuenta", entidad_id=cuenta.pk).exists())


class AuthControllerTests(TestCase):
    def setUp(self):
        self.cuenta = crear_cuenta()

    def test_pantalla_de_login(self):
        respuesta = self.client.get(reverse("identidad:login"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Iniciar sesión")

    def test_login_correcto_abre_sesion(self):
        respuesta = self.client.post(reverse("identidad:login"),
                                     {"correo": "ana@unsa.edu.pe", "password": "secreta123"})
        self.assertRedirects(respuesta, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"].replace("-", ""), 16), self.cuenta.pk.int)

    def test_login_incorrecto_muestra_error(self):
        respuesta = self.client.post(reverse("identidad:login"),
                                     {"correo": "ana@unsa.edu.pe", "password": "mal"})
        self.assertContains(respuesta, "Correo o contraseña incorrectos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_solicitante_sin_is_staff_tambien_entra(self):
        self.assertFalse(self.cuenta.is_staff)
        self.client.post(reverse("identidad:login"), {"correo": "ana@unsa.edu.pe", "password": "secreta123"})
        self.assertEqual(self.client.get(reverse("sanciones:lista")).status_code, 200)

    def test_vista_protegida_redirige_al_login_propio(self):
        respuesta = self.client.get(reverse("sanciones:lista"))
        self.assertRedirects(respuesta, f"{reverse('identidad:login')}?next={reverse('sanciones:lista')}")

    def test_next_externo_se_ignora(self):
        respuesta = self.client.post(
            reverse("identidad:login"),
            {"correo": "ana@unsa.edu.pe", "password": "secreta123", "next": "https://malo.com/"},
        )
        self.assertRedirects(respuesta, reverse("home"))

    def test_logout(self):
        self.client.force_login(self.cuenta)
        respuesta = self.client.post(reverse("identidad:logout"))
        self.assertRedirects(respuesta, reverse("identidad:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class CuentasControllerTests(TestCase):
    def test_solo_el_administrador_ve_cuentas(self):
        self.client.force_login(crear_cuenta(roles=[RolSistema.SOLICITANTE]))
        self.assertEqual(self.client.get(reverse("identidad:cuentas")).status_code, 403)

    def test_administrador_asigna_rol(self):
        admin = crear_cuenta("admin@unsa.edu.pe", "70000002", roles=[RolSistema.ADMINISTRADOR])
        otra = crear_cuenta()
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("identidad:cuentas")).status_code, 200)
        self.client.post(reverse("identidad:asignar_rol", args=[otra.pk]), {"rol": RolSistema.ENCARGADO})
        otra.refresh_from_db()
        self.assertEqual(otra.roles, [RolSistema.ENCARGADO])
