"""seed_entrega deja los mínimos que pidió la docente para la revisión."""
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.catalogo.models import Item
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoItem, EstadoPrestamo, EstadoReserva, TipoUsuario
from apps.identidad.models import PerfilSolicitante
from apps.reservas.dominio.models import Reserva

LIMA = ZoneInfo("America/Lima")
LUNES_10AM = datetime(2026, 11, 30, 10, 0, tzinfo=LIMA)
MARTES_11AM = datetime(2026, 12, 1, 11, 0, tzinfo=LIMA)


def correr(ahora=LUNES_10AM):
    call_command("seed_entrega", ahora=ahora, stdout=io.StringIO())


class SeedEntregaTests(TestCase):
    def test_minimos_de_la_revision(self):
        correr()
        perfiles = PerfilSolicitante.objects
        self.assertGreaterEqual(perfiles.filter(tipo=TipoUsuario.DOCENTE).count(), 5)
        self.assertGreaterEqual(perfiles.filter(tipo=TipoUsuario.ADMINISTRATIVO).count(), 2)
        self.assertGreater(perfiles.filter(tipo=TipoUsuario.ALUMNO).count(), 0)
        self.assertEqual(Item.objects.count(), 20)
        self.assertTrue(Item.objects.filter(categoria__es_especial=True).exists())

        activos = Prestamo.objects.filter(estado=EstadoPrestamo.ACTIVO)
        self.assertEqual(activos.count(), 5)
        self.assertEqual(Item.objects.filter(estado=EstadoItem.PRESTADO).count(), 5)
        for p in activos:
            self.assertEqual(Reserva.objects.get(pk=p.reserva_id).estado, EstadoReserva.ATENDIDA)
            self.assertTrue(p.garantia_tipo and p.terminos_aceptados)
            self.assertGreater(p.fecha_vencimiento, LUNES_10AM)
        self.assertGreater(Prestamo.objects.filter(estado=EstadoPrestamo.DEVUELTO).count(), 0)

    def test_correos_unsa_y_sin_duplicar_al_correrlo_dos_veces(self):
        correr()
        cuentas, prestamos, items = get_user_model().objects.count(), Prestamo.objects.count(), Item.objects.count()
        correr()
        self.assertEqual(get_user_model().objects.count(), cuentas)
        self.assertEqual(Prestamo.objects.count(), prestamos)
        self.assertEqual(Item.objects.count(), items)
        self.assertFalse(get_user_model().objects.exclude(correo__endswith="@unsa.edu.pe").exists())

    def test_al_dia_siguiente_cierra_los_activos_viejos_y_crea_los_de_hoy(self):
        correr(LUNES_10AM)
        correr(MARTES_11AM)
        activos = Prestamo.objects.filter(estado=EstadoPrestamo.ACTIVO)
        self.assertEqual(activos.count(), 5)
        self.assertTrue(all(p.fecha_entrega.astimezone(LIMA).date() == MARTES_11AM.date() for p in activos))
        self.assertEqual(Item.objects.filter(estado=EstadoItem.PRESTADO).count(), 5)
