import uuid

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.catalogo.aplicacion.dtos import NuevoItemDTO
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import EstadoItem, EstadoReserva
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
from apps.reservas.dominio.servicios import AsignadorDeCola


class _R:  # reserva falsa para probar el servicio de dominio sin base de datos
    def __init__(self, pos, estado="ACTIVA"):
        self.posicion_en_cola, self.estado = pos, estado


class AsignadorDeColaTests(TestCase):
    def test_siguiente_es_el_primero_activo(self):
        cola = [_R(3), _R(1, "CANCELADA"), _R(2)]
        self.assertEqual(AsignadorDeCola.siguiente(cola).posicion_en_cola, 2)

    def test_nueva_va_al_final(self):
        self.assertEqual(AsignadorDeCola.posicion_para_nueva([_R(1), _R(2)]), 3)
        self.assertEqual(AsignadorDeCola.posicion_para_nueva([]), 1)


class ReservaServicioTests(TestCase):
    def setUp(self):
        catalogo = CatalogoServicioAplicacion()
        cat = catalogo.crear_categoria("Libros")
        self.item = catalogo.registrar_item(NuevoItemDTO(codigo="LIB-1", categoria_id=cat.id))
        catalogo.cambiar_estado_item(self.item.id, EstadoItem.PRESTADO)
        self.s = ReservaServicioAplicacion()
        self.ana, self.beto = uuid.uuid4(), uuid.uuid4()

    def test_cola_fifo(self):
        r1 = self.s.crear(self.item.id, self.ana)
        r2 = self.s.crear(self.item.id, self.beto)
        self.assertEqual((r1.posicion_en_cola, r2.posicion_en_cola), (1, 2))

    def test_no_dos_reservas_activas_del_mismo_solicitante(self):
        self.s.crear(self.item.id, self.ana)
        with self.assertRaises(ValidationError):
            self.s.crear(self.item.id, self.ana)

    def test_no_se_reserva_un_item_disponible(self):
        CatalogoServicioAplicacion().cambiar_estado_item(self.item.id, EstadoItem.DISPONIBLE)
        with self.assertRaises(ValidationError):
            self.s.crear(self.item.id, self.ana)

    def test_asignar_siguiente_confirma_y_notifica(self):
        r1 = self.s.crear(self.item.id, self.ana)
        self.s.crear(self.item.id, self.beto)
        asignada = self.s.asignar_siguiente(self.item.id)
        self.assertEqual(asignada.id, r1.id)
        self.assertEqual(asignada.estado, EstadoReserva.CONFIRMADA)
        # Se registró la notificación para Ana (sin cuenta real no hay correo que enviar)
        from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
        self.assertEqual(len(NotificacionServicioAplicacion().mis_notificaciones(self.ana)), 1)

    def test_no_se_confirma_una_cancelada(self):
        r = self.s.crear(self.item.id, self.ana)
        self.s.cancelar(r.id)
        with self.assertRaises(ValidationError):
            self.s.confirmar(r.id)
