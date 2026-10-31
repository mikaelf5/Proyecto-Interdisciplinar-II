import uuid
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoItem, EstadoPrestamo, RolSistema
from apps.perdidas.dominio.models import CasoPerdida
from apps.sanciones.tests.helpers import crear_cuenta, crear_item, crear_prestamo


class RegistrarPerdidaTests(TestCase):
    """RF-G3: registrar la pérdida cierra el préstamo y da de baja el ítem."""

    def setUp(self):
        self.encargado = crear_cuenta(roles=[RolSistema.ENCARGADO])
        self.ana = crear_cuenta(roles=[RolSistema.SOLICITANTE])
        self.catalogo = CatalogoServicioAplicacion()
        self.item = crear_item("EQP-001", "Laptop")
        self.catalogo.marcar_prestado(self.item.id)
        self.prestamo = crear_prestamo(self.item.id, self.ana.pk)
        self.client.force_login(self.encargado)
        self.url = reverse("perdidas:crear")

    def post(self, **extra):
        datos = dict(prestamo_id=str(self.prestamo.id), solicitante_id="",
                     fecha=date.today().isoformat(), observaciones="Se perdió en el laboratorio",
                     costo_estimado="3500")
        datos.update(extra)
        return self.client.post(self.url, datos)

    def estado_item(self):
        return self.catalogo.obtener_item(self.item.id)

    def test_cierra_el_prestamo_y_da_de_baja_el_item(self):
        r = self.post()
        self.assertRedirects(r, reverse("perdidas:lista"))
        caso = CasoPerdida.objects.get()
        self.assertEqual(caso.solicitante_id, self.ana.pk)        # se toma del préstamo
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.estado, EstadoPrestamo.CERRADO_POR_PERDIDA)
        item = self.estado_item()
        self.assertEqual(item.estado, EstadoItem.BAJA)
        self.assertIn("Pérdida", item.motivo_fuera_servicio)

    def test_deja_constancia_en_auditoria(self):
        self.post()
        registros = {(r.accion, r.entidad): r for r in RegistroAuditoria.objects.all()}
        self.assertEqual(set(registros), {
            ("ITEM_DANIADO", "CasoPerdida"), ("CAMBIO_ESTADO", "Prestamo"), ("CAMBIO_ESTADO", "Item")})
        self.assertTrue(all(r.actor_id == self.encargado.pk for r in registros.values()))
        self.assertEqual(registros[("CAMBIO_ESTADO", "Item")].entidad_id, self.item.id)

    def test_prestamo_inexistente(self):
        r = self.post(prestamo_id=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No existe el préstamo")
        self.assertEqual(CasoPerdida.objects.count(), 0)

    def test_prestamo_ya_devuelto_no_se_puede_perder(self):
        self.prestamo.estado = EstadoPrestamo.DEVUELTO
        self.prestamo.save()
        r = self.post()
        self.assertContains(r, "préstamo abierto")
        self.assertEqual(CasoPerdida.objects.count(), 0)
        self.assertEqual(self.estado_item().estado, EstadoItem.PRESTADO)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_solicitante_distinto_deshace_todo(self):
        r = self.post(solicitante_id=str(uuid.uuid4()))
        self.assertContains(r, "no coincide")
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.estado, EstadoPrestamo.ACTIVO)      # transacción: nada a medias
        self.assertEqual(self.estado_item().estado, EstadoItem.PRESTADO)
        self.assertEqual(CasoPerdida.objects.count(), 0)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_solicitante_igual_al_del_prestamo_es_valido(self):
        self.post(solicitante_id=str(self.ana.pk))
        self.assertEqual(CasoPerdida.objects.count(), 1)

    def test_item_ya_dado_de_baja_no_falla(self):
        self.catalogo.dar_de_baja_item(self.item.id, "Obsoleto")
        self.post()
        self.assertEqual(CasoPerdida.objects.count(), 1)
        self.assertEqual(self.estado_item().estado, EstadoItem.BAJA)

    def test_cerrar_caso_y_eliminar(self):
        self.post()
        caso = CasoPerdida.objects.get()
        self.client.post(reverse("perdidas:cerrar", args=[caso.pk]))
        caso.refresh_from_db()
        self.assertTrue(caso.cerrado)
        self.client.post(reverse("perdidas:eliminar", args=[caso.pk]))
        self.assertEqual(CasoPerdida.objects.count(), 0)

    def test_solo_encargado_o_administrador(self):
        for rol, esperado in ((RolSistema.SOLICITANTE, 403), (RolSistema.SUPERVISOR, 403),
                              (RolSistema.ENCARGADO, 200), (RolSistema.ADMINISTRADOR, 200)):
            self.client.force_login(crear_cuenta(roles=[rol]))
            self.assertEqual(self.client.get(reverse("perdidas:lista")).status_code, esperado, rol)
