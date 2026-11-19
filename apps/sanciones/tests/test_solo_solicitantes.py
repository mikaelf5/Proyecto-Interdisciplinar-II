"""Observación de la docente: sancionar eligiendo a la persona por nombre, y solo a solicitantes."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.common.choices import EstadoPrestamo, RolSistema
from apps.sanciones.models import Sancion

from .helpers import crear_cuenta, crear_item, crear_prestamo

HOY = date.today()


class SancionarPorNombreTests(TestCase):
    def setUp(self):
        self.encargado = crear_cuenta(nombres="Elena Encargada", roles=[RolSistema.ENCARGADO])
        self.ana = crear_cuenta(nombres="Ana Alumna", roles=[RolSistema.SOLICITANTE])
        self.client.force_login(self.encargado)

    def _crear(self, **campos):
        datos = dict(prestamo_id="", tipo="OBSERVACION", motivo="Devolvió tarde el ítem",
                     duracion_dias="", fecha_inicio=HOY.isoformat())
        datos.update(campos)
        return self.client.post(reverse("sanciones:crear"), datos)

    def test_el_formulario_ofrece_solo_solicitantes_con_nombre_y_dni(self):
        r = self.client.get(reverse("sanciones:crear"))
        opciones = dict(r.context["form"].fields["solicitante_id"].choices)
        self.assertIn(str(self.ana.pk), opciones)
        self.assertIn("Ana Alumna", opciones[str(self.ana.pk)])
        self.assertIn(f"DNI {self.ana.dni}", opciones[str(self.ana.pk)])
        self.assertNotIn(str(self.encargado.pk), opciones)

    def test_no_se_puede_sancionar_a_quien_no_es_solicitante(self):
        r = self._crear(solicitante_id=str(self.encargado.pk))
        self.assertEqual(r.status_code, 200)   # vuelve el formulario con el error
        self.assertTrue(r.context["form"].errors["solicitante_id"])
        self.assertEqual(Sancion.objects.count(), 0)

    def test_sancionar_a_un_solicitante(self):
        self._crear(solicitante_id=str(self.ana.pk))
        self.assertEqual(Sancion.objects.get().solicitante_id, self.ana.pk)

    def test_el_prestamo_se_elige_por_fecha_e_item_y_debe_ser_del_solicitante(self):
        item = crear_item("EQP-050", "Proyector")
        de_ana = crear_prestamo(item.id, self.ana.pk, estado=EstadoPrestamo.DEVUELTO)
        otro = crear_cuenta(nombres="Diego Docente", roles=[RolSistema.SOLICITANTE])
        de_otro = crear_prestamo(crear_item("EQP-051", "Cámara").id, otro.pk, estado=EstadoPrestamo.DEVUELTO)

        etiquetas = dict(self.client.get(reverse("sanciones:crear")).context["form"].fields["prestamo_id"].choices)
        self.assertIn("EQP-050 Proyector", etiquetas[str(de_ana.pk)])

        r = self._crear(solicitante_id=str(self.ana.pk), prestamo_id=str(de_otro.pk))
        self.assertTrue(r.context["form"].errors["prestamo_id"])
        self._crear(solicitante_id=str(self.ana.pk), prestamo_id=str(de_ana.pk))
        self.assertEqual(Sancion.objects.get().prestamo_id, de_ana.pk)

    def test_la_lista_busca_por_nombre_y_dni_y_muestra_el_nombre(self):
        Sancion.objects.create(solicitante_id=self.ana.pk, aplicada_por_id=self.encargado.pk,
                               tipo="OBSERVACION", motivo="Atraso", fecha_inicio=HOY)
        url = reverse("sanciones:lista")
        for q in ("ana alu", self.ana.dni):
            r = self.client.get(url, {"q": q})
            self.assertEqual(r.context["total"], 1, q)
            self.assertContains(r, "Ana Alumna")
        self.assertEqual(self.client.get(url, {"q": "Nadie"}).context["total"], 0)
