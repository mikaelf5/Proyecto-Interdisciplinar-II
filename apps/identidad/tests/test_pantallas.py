"""Pruebas de INTEGRACIÓN: pantallas + capas reales + PostgreSQL.

Cubren lo que pidió el reparto: registro, recuperación de contraseña y
etiquetas; además gestión de cuentas, Mi perfil, menú por rol y seed_cuentas.
"""
import re
import uuid
import os
from datetime import date, timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.common.choices import EstadoPrestamo, EtiquetaEstado, RolSistema, TipoUsuario
from apps.identidad.fabrica import cuenta_servicio
from apps.identidad.models import Cuenta, PerfilSolicitante
from apps.sanciones.dominio.models import Sancion, TipoSancion
from apps.sanciones.tests.helpers import crear_prestamo


def crear(correo, dni, roles, password="Clave-Segura-1", perfil=None, **extra):
    cuenta = Cuenta.objects.create_user(correo, "Persona Prueba", dni, password, roles=list(roles), **extra)
    if perfil:
        PerfilSolicitante.objects.create(
            cuenta=cuenta, tipo=perfil, cui="20230001", habilitado_institucional=True,
            acta_version="v1", acta_fecha_firma=date.today())
    return cuenta


def datos_registro(**extra):
    datos = {
        "nombres": "Luis Quispe Mamani", "dni": "71234567", "correo": "lquispe@unsa.edu.pe",
        "celular": "987654321", "direccion": "Av. Independencia 123",
        "roles": [RolSistema.SOLICITANTE], "tipo": TipoUsuario.ALUMNO, "cui": "20231234",
        "habilitado_institucional": "on", "acta_aceptada": "on",
        "password1": "Arequipa-2026", "password2": "Arequipa-2026",
        "consentimiento_aceptado": "on",
    }
    datos.update(extra)
    return datos


class RegistroTests(TestCase):
    """RF-B1, RF-B2, RNF-2: el administrador registra usuarios."""

    def setUp(self):
        self.admin = crear("admin@unsa.edu.pe", "70000000", [RolSistema.ADMINISTRADOR])
        self.client.force_login(self.admin)

    def test_solo_el_administrador_registra(self):
        self.client.force_login(crear("enc@unsa.edu.pe", "70000003", [RolSistema.ENCARGADO]))
        self.assertEqual(self.client.get(reverse("identidad:registrar")).status_code, 403)

    def test_formulario_muestra_acta_y_ley_29733(self):
        respuesta = self.client.get(reverse("identidad:registrar"))
        self.assertContains(respuesta, "Acta de responsabilidad (v1)")
        self.assertContains(respuesta, "29733")

    def test_registro_completo(self):
        respuesta = self.client.post(reverse("identidad:registrar"), datos_registro())
        cuenta = Cuenta.objects.get(correo="lquispe@unsa.edu.pe")
        self.assertRedirects(respuesta, reverse("identidad:cuenta_detalle", args=[cuenta.pk]))
        self.assertEqual(cuenta.roles, [RolSistema.SOLICITANTE])
        self.assertTrue(cuenta.check_password("Arequipa-2026"))
        self.assertEqual(cuenta.consentimiento_version, "v1")
        perfil = cuenta.perfil
        self.assertEqual((perfil.tipo, perfil.cui, perfil.acta_version), (TipoUsuario.ALUMNO, "20231234", "v1"))
        self.assertEqual(perfil.acta_fecha_firma, timezone.localdate())
        self.assertTrue(cuenta_servicio().consultar_habilitacion(cuenta.pk))
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="Cuenta", entidad_id=cuenta.pk,
                                                         actor_id=self.admin.pk).exists())

    def test_errores_de_formato(self):
        respuesta = self.client.post(reverse("identidad:registrar"), datos_registro(
            dni="12ab", celular="12345", password2="otra-cosa", consentimiento_aceptado=""))
        self.assertContains(respuesta, "8 dígitos")
        self.assertContains(respuesta, "empezar con 9")
        self.assertContains(respuesta, "no coinciden")
        self.assertFalse(Cuenta.objects.filter(correo="lquispe@unsa.edu.pe").exists())

    def test_contrasena_debil(self):
        respuesta = self.client.post(reverse("identidad:registrar"),
                                     datos_registro(password1="12345678", password2="12345678"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Cuenta.objects.filter(correo="lquispe@unsa.edu.pe").exists())

    def test_reglas_de_negocio_vuelven_al_campo(self):
        crear("otro@unsa.edu.pe", "71234567", [RolSistema.SOLICITANTE])
        respuesta = self.client.post(reverse("identidad:registrar"), datos_registro(
            consentimiento_aceptado="", acta_aceptada=""))
        self.assertContains(respuesta, "Ya existe una cuenta con ese DNI")
        self.assertContains(respuesta, "Sin el consentimiento")
        self.assertContains(respuesta, "firmar el acta")
        self.assertEqual(PerfilSolicitante.objects.count(), 0)  # todo o nada

    def test_registrar_personal_sin_perfil(self):
        self.client.post(reverse("identidad:registrar"), datos_registro(
            roles=[RolSistema.SUPERVISOR], tipo="", cui="", acta_aceptada=""))
        cuenta = Cuenta.objects.get(correo="lquispe@unsa.edu.pe")
        self.assertEqual(cuenta.roles, [RolSistema.SUPERVISOR])
        self.assertFalse(PerfilSolicitante.objects.filter(cuenta=cuenta).exists())


class RecuperarContrasenaTests(TestCase):
    """RF-B4: PasswordResetView; el correo sale por consola (en pruebas, mail.outbox)."""

    def setUp(self):
        self.ana = crear("ana@unsa.edu.pe", "70000001", [RolSistema.SOLICITANTE])

    def test_enlace_en_el_login(self):
        self.assertContains(self.client.get(reverse("identidad:login")), reverse("identidad:password_reset"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_flujo_completo(self):
        respuesta = self.client.post(reverse("identidad:password_reset"), {"email": "ANA@unsa.edu.pe"})
        self.assertRedirects(respuesta, reverse("identidad:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["ana@unsa.edu.pe"])
        self.assertIn("Recupera tu contraseña", correo.subject)

        enlace = re.search(r"https?://[^/]+(/\S+)", correo.body).group(1)
        respuesta = self.client.get(enlace, follow=True)  # Django cambia el token por "set-password"
        self.assertContains(respuesta, "Crea tu nueva contraseña")
        respuesta = self.client.post(respuesta.redirect_chain[-1][0], {
            "new_password1": "Nueva-Clave-2026", "new_password2": "Nueva-Clave-2026"})
        self.assertRedirects(respuesta, reverse("identidad:password_reset_complete"))

        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password("Nueva-Clave-2026"))
        self.assertEqual(self.client.get(enlace, follow=True).context["validlink"], False)  # un solo uso

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_correo_desconocido_no_revela_nada(self):
        respuesta = self.client.post(reverse("identidad:password_reset"), {"email": "nadie@unsa.edu.pe"})
        self.assertRedirects(respuesta, reverse("identidad:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cuenta_desactivada_no_recibe_correo(self):
        self.ana.is_active = False
        self.ana.save()
        self.client.post(reverse("identidad:password_reset"), {"email": "ana@unsa.edu.pe"})
        self.assertEqual(len(mail.outbox), 0)

    def test_cambiar_contrasena_con_sesion(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(reverse("identidad:password_change"), {
            "old_password": "Clave-Segura-1",
            "new_password1": "Otra-Clave-2026", "new_password2": "Otra-Clave-2026"})
        self.assertRedirects(respuesta, reverse("identidad:password_change_done"))
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password("Otra-Clave-2026"))


@override_settings(IDENTIDAD_PRESTAMOS_PARA_FRECUENTE=3)
class EtiquetasIntegracionTests(TestCase):
    """RF-B6 con las tablas reales de Circulación y Sanciones."""

    def setUp(self):
        self.ana = crear("ana@unsa.edu.pe", "70000001", [RolSistema.SOLICITANTE], perfil=TipoUsuario.ALUMNO)
        self.encargado = crear("enc@unsa.edu.pe", "70000003", [RolSistema.ENCARGADO])

    def devolver(self, a_tiempo=True):
        entrega = timezone.now() - timedelta(days=2)
        vence = entrega + timedelta(hours=4)
        devuelto = vence - timedelta(hours=1) if a_tiempo else vence + timedelta(hours=3)
        crear_prestamo(uuid.uuid4(), self.ana.pk, estado=EstadoPrestamo.DEVUELTO,
                       entrega=entrega, vence=vence, devuelto=devuelto)

    def sancionar(self, tipo, **extra):
        return Sancion.objects.create(solicitante_id=self.ana.pk, aplicada_por_id=self.encargado.pk,
                                      tipo=tipo, motivo="Atraso", fecha_inicio=date.today(), **extra)

    def etiqueta(self):
        return cuenta_servicio().actualizar_etiqueta(self.ana.pk)

    def test_frecuente_solo_cuenta_devoluciones_a_tiempo(self):
        self.devolver()
        self.devolver()
        self.devolver(a_tiempo=False)
        crear_prestamo(uuid.uuid4(), self.ana.pk)  # activo: no cuenta
        self.assertEqual(self.etiqueta(), EtiquetaEstado.NUEVO)
        self.devolver()
        self.assertEqual(self.etiqueta(), EtiquetaEstado.FRECUENTE)
        self.assertTrue(RegistroAuditoria.objects.filter(entidad_id=self.ana.pk, motivo__contains="Frecuente").exists())

    def test_sancionado_y_baneado(self):
        suspension = self.sancionar(TipoSancion.SUSPENSION_TEMPORAL, duracion_dias=7)
        self.assertEqual(self.etiqueta(), EtiquetaEstado.SANCIONADO)
        baneo = self.sancionar(TipoSancion.BANEO)
        self.assertEqual(self.etiqueta(), EtiquetaEstado.BANEADO)
        baneo.levantar()
        suspension.levantar()
        self.assertEqual(self.etiqueta(), EtiquetaEstado.NUEVO)

    def test_sancion_vencida_ya_no_cuenta(self):
        Sancion.objects.create(solicitante_id=self.ana.pk, aplicada_por_id=self.encargado.pk,
                               tipo=TipoSancion.SUSPENSION_TEMPORAL, motivo="x", duracion_dias=3,
                               fecha_inicio=date.today() - timedelta(days=10))
        self.assertEqual(self.etiqueta(), EtiquetaEstado.NUEVO)

    def test_circulacion_ve_la_sancion_al_instante(self):
        self.sancionar(TipoSancion.BANEO)
        resultado = cuenta_servicio().consultar_habilitacion(self.ana.pk)
        self.assertFalse(resultado)
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.etiqueta, EtiquetaEstado.BANEADO)

    def test_comando_actualizar_etiquetas(self):
        self.sancionar(TipoSancion.OBSERVACION)
        call_command("actualizar_etiquetas", stdout=open(os.devnull, "w"))
        self.ana.perfil.refresh_from_db()
        self.assertEqual(self.ana.perfil.etiqueta, EtiquetaEstado.SANCIONADO)


class GestionCuentasPantallaTests(TestCase):
    def setUp(self):
        self.admin = crear("admin@unsa.edu.pe", "70000000", [RolSistema.ADMINISTRADOR])
        self.ana = crear("ana@unsa.edu.pe", "70000001", [RolSistema.SOLICITANTE, RolSistema.ENCARGADO],
                         perfil=TipoUsuario.ALUMNO)
        self.client.force_login(self.admin)

    def test_detalle_y_filtros(self):
        self.assertContains(self.client.get(reverse("identidad:cuenta_detalle", args=[self.ana.pk])),
                            "Puede solicitar préstamos")
        lista = self.client.get(reverse("identidad:cuentas"), {"rol": RolSistema.ADMINISTRADOR})
        self.assertEqual(list(lista.context["cuentas"]), [self.admin])

    def test_quitar_rol(self):
        self.client.post(reverse("identidad:quitar_rol", args=[self.ana.pk]), {"rol": RolSistema.ENCARGADO})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.roles, [RolSistema.SOLICITANTE])

    def test_no_puede_quitarse_su_rol(self):
        respuesta = self.client.post(reverse("identidad:quitar_rol", args=[self.admin.pk]),
                                     {"rol": RolSistema.ADMINISTRADOR}, follow=True)
        self.assertContains(respuesta, "No puedes quitarte tu propio rol")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.tiene_rol(RolSistema.ADMINISTRADOR))

    def test_desactivar_sin_motivo_y_con_motivo(self):
        url = reverse("identidad:desactivar", args=[self.ana.pk])
        self.assertContains(self.client.post(url, {"motivo": ""}, follow=True), "Indica el motivo")
        self.client.post(url, {"motivo": "Egresó de la escuela"})
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_active)
        self.client.logout()
        respuesta = self.client.post(reverse("identidad:login"),
                                     {"correo": "ana@unsa.edu.pe", "password": "Clave-Segura-1"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(respuesta.status_code, 200)

    def test_activar(self):
        self.ana.is_active = False
        self.ana.save()
        self.client.post(reverse("identidad:activar", args=[self.ana.pk]))
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_retirar_y_confirmar_habilitacion(self):
        url = reverse("identidad:habilitacion", args=[self.ana.pk])
        self.client.post(url, {"habilitado": "0", "motivo": "Matrícula no vigente"})
        self.assertFalse(cuenta_servicio().consultar_habilitacion(self.ana.pk))
        self.client.post(url, {"habilitado": "1"})
        self.assertTrue(cuenta_servicio().consultar_habilitacion(self.ana.pk))

    def test_completar_perfil(self):
        enc = crear("enc@unsa.edu.pe", "70000003", [RolSistema.ENCARGADO])
        self.client.post(reverse("identidad:completar_perfil", args=[enc.pk]), {
            "tipo": TipoUsuario.ADMINISTRATIVO, "acta_aceptada": "on", "habilitado_institucional": "on"})
        enc.refresh_from_db()
        self.assertTrue(enc.tiene_rol(RolSistema.SOLICITANTE))
        self.assertEqual(enc.perfil.acta_version, "v1")

    def test_administrador_sin_superusuario_entra_a_politicas(self):
        nuevo = crear("admin2@unsa.edu.pe", "70000002", [])
        self.client.post(reverse("identidad:asignar_rol", args=[nuevo.pk]), {"rol": RolSistema.ADMINISTRADOR})
        nuevo.refresh_from_db()
        self.assertTrue(nuevo.is_staff)
        self.client.force_login(nuevo)
        self.assertEqual(self.client.get(reverse("admin:politicas_politicaprestamo_changelist")).status_code, 200)

    def test_tipo_usuario_de(self):
        self.assertEqual(cuenta_servicio().tipo_usuario_de(self.ana.pk), TipoUsuario.ALUMNO)
        self.assertIsNone(cuenta_servicio().tipo_usuario_de(self.admin.pk))

    def test_reservas_usa_tipo_usuario_de(self):
        from apps.reservas.infraestructura.adaptadores import IdentidadAdaptador
        self.assertEqual(IdentidadAdaptador().tipo_usuario(self.ana.pk), TipoUsuario.ALUMNO)


class MiPerfilTests(TestCase):
    def setUp(self):
        self.ana = crear("ana@unsa.edu.pe", "70000001", [RolSistema.SOLICITANTE], perfil=TipoUsuario.ALUMNO)
        self.client.force_login(self.ana)

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("identidad:mi_perfil")).status_code, 302)

    def test_muestra_datos_y_estado(self):
        respuesta = self.client.get(reverse("identidad:mi_perfil"))
        self.assertContains(respuesta, "70000001")
        self.assertContains(respuesta, "Puedes solicitar préstamos")

    def test_muestra_motivos_si_no_esta_habilitado(self):
        self.ana.perfil.habilitado_institucional = False
        self.ana.perfil.save()
        self.assertContains(self.client.get(reverse("identidad:mi_perfil")), "condición institucional")

    def test_actualiza_contacto(self):
        self.client.post(reverse("identidad:mi_perfil"), {"celular": "912345678", "direccion": "Cayma"})
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.celular, self.ana.direccion), ("912345678", "Cayma"))
        respuesta = self.client.post(reverse("identidad:mi_perfil"), {"celular": "123", "direccion": ""})
        self.assertContains(respuesta, "empezar con 9")


class MenuPorRolTests(TestCase):
    def menu(self, *roles, correo="x@unsa.edu.pe"):
        self.client.force_login(crear(correo, str(70000100 + len(correo)), roles))
        return self.client.get(reverse("identidad:mi_perfil")).content.decode()

    def test_solicitante(self):
        html = self.menu(RolSistema.SOLICITANTE)

        for texto in ("Catálogo", "Mis reservas", "Notificaciones", "Mi perfil"):
            self.assertIn(texto, html)

        for url in (
                reverse("circulacion:entregas_hoy"),
                reverse("circulacion:devoluciones"),
                reverse("circulacion:prestamos_vencidos"),
                reverse("reservas:bandeja_supervisor"),
                reverse("identidad:cuentas"),
                reverse("reportes:lista"),
        ):
            self.assertNotIn(f'href="{url}"', html)

    def test_encargado_ve_prestamos(self):
        html = self.menu(RolSistema.ENCARGADO)

        self.assertIn(
            f'href="{reverse("circulacion:entregas_hoy")}"',
            html
        )

        self.assertNotIn(
            f'href="{reverse("identidad:cuentas")}"',
            html
        )

    def test_supervisor_ve_su_bandeja(self):
        html = self.menu(RolSistema.SUPERVISOR)

        self.assertIn(
            f'href="{reverse("reservas:bandeja_supervisor")}"',
            html
        )

        self.assertNotIn(
            f'href="{reverse("circulacion:entregas_hoy")}"',
            html
        )
    def test_administrador(self):
        html = self.menu(RolSistema.ADMINISTRADOR)
        for url in (reverse("identidad:cuentas"), reverse("reportes:lista"),
                    reverse("admin:app_list", kwargs={"app_label": "politicas"})):
            self.assertIn(f'href="{url}"', html)

    def test_sin_sesion_solo_login(self):
        html = self.client.get(reverse("identidad:login")).content.decode()
        self.assertNotIn("Mis reservas", html)


class SeedCuentasTests(TestCase):
    def test_crea_una_por_rol_y_se_puede_repetir(self):
        call_command("seed_cuentas", stdout=open(os.devnull, "w"))
        call_command("seed_cuentas", stdout=open(os.devnull, "w"))
        self.assertEqual(Cuenta.objects.count(), 6)
        for rol in RolSistema.values:
            self.assertTrue(Cuenta.objects.filter(roles__contains=[rol]).exists(), rol)
        respuesta = self.client.post(reverse("identidad:login"),
                                     {"correo": "ana@demo.pe", "password": "demo1234"})
        self.assertRedirects(respuesta, reverse("home"))
        self.assertTrue(cuenta_servicio().consultar_habilitacion(Cuenta.objects.get(correo="ana@demo.pe").pk))
        self.assertFalse(cuenta_servicio().consultar_habilitacion(Cuenta.objects.get(correo="pedro@demo.pe").pk))

    def test_convive_con_seed_demo(self):
        call_command("seed_cuentas", stdout=open(os.devnull, "w"))
        call_command("seed_demo", stdout=open(os.devnull, "w"))
        self.assertEqual(Cuenta.objects.filter(correo__endswith="@demo.pe").count(), 6)
