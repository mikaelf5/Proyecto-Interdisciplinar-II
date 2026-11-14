"""Auditoría: que las acciones clave de los otros módulos realmente queden registradas (RF-J2)
y que el reporte de "perdidos o dañados" las vea."""
import uuid
from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.auditoria.dominio.constantes import SISTEMA_ID
from apps.auditoria.dominio.models import RegistroAuditoria
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.aplicacion.dtos import DevolucionDTO
from apps.circulacion.dominio.models import Prestamo
from apps.circulacion.fabrica import prestamo_servicio
from apps.common.choices import EstadoItem, EstadoReserva, RolSistema
from apps.reportes.dominio.models import Reporte, TipoReporte
from apps.reportes.fabrica import reporte_servicio
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
from apps.reservas.dominio.models import Reserva
from apps.sanciones.tests.helpers import crear_cuenta, crear_item, crear_prestamo


def registros(**filtros):
    return list(RegistroAuditoria.objects.filter(**filtros).order_by("fecha_hora"))


class CatalogoAuditaTests(TestCase):
    """Botones del encargado en el detalle del ítem."""

    def setUp(self):
        self.encargado = crear_cuenta(roles=[RolSistema.ENCARGADO])
        self.client.force_login(self.encargado)
        self.item = crear_item("EQP-001", "Laptop")
        self.catalogo = CatalogoServicioAplicacion()

    def estado(self):
        return self.catalogo.obtener_item(self.item.id).estado

    def test_marcar_daniado_queda_con_quien_lo_hizo_y_el_motivo(self):
        self.client.post(reverse("catalogo:marcar_daniado", args=[self.item.id]), {"motivo": "Pantalla rota"})
        self.assertEqual(self.estado(), EstadoItem.MANTENIMIENTO)
        reg = registros(accion="ITEM_DANIADO").pop()
        self.assertEqual((reg.actor_id, reg.entidad, reg.entidad_id, reg.motivo),
                         (self.encargado.pk, "Item", self.item.id, "Pantalla rota"))

    def test_poner_disponible_deja_el_cambio_de_estado(self):
        self.catalogo.cambiar_estado_item(self.item.id, EstadoItem.MANTENIMIENTO, "Revisión")
        self.client.post(reverse("catalogo:poner_disponible", args=[self.item.id]))
        reg = registros(accion="CAMBIO_ESTADO").pop()
        self.assertEqual((reg.actor_id, reg.entidad_id), (self.encargado.pk, self.item.id))
        self.assertIn("Mantenimiento → Disponible", reg.motivo)

    def test_dar_de_baja_deja_el_motivo(self):
        self.client.post(reverse("catalogo:dar_de_baja", args=[self.item.id]), {"motivo": "Obsoleto"})
        self.assertEqual(self.estado(), EstadoItem.BAJA)
        reg = registros(accion="CAMBIO_ESTADO").pop()
        self.assertEqual(reg.actor_id, self.encargado.pk)
        self.assertIn("Dado de baja: Obsoleto", reg.motivo)

    def test_sin_motivo_no_cambia_nada_ni_audita(self):
        self.client.post(reverse("catalogo:marcar_daniado", args=[self.item.id]), {"motivo": ""})
        self.assertEqual(self.estado(), EstadoItem.DISPONIBLE)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_si_lo_dispara_otro_modulo_el_dano_sale_como_sistema_y_lo_demas_no_se_duplica(self):
        """Circulación llama marcar_daniado sin actor; Pérdidas llama dar_de_baja_item sin actor."""
        self.catalogo.marcar_daniado(self.item.id, "Golpe en la devolución")
        self.assertEqual(registros(accion="ITEM_DANIADO").pop().actor_id, SISTEMA_ID)
        otro = crear_item("EQP-002", "Cámara")
        self.catalogo.dar_de_baja_item(otro.id, "Pérdida: se extravió")       # sin actor: no audita aquí
        self.assertEqual(RegistroAuditoria.objects.count(), 1)


class ReservasAuditaTests(TestCase):
    def setUp(self):
        self.supervisor = crear_cuenta(roles=[RolSistema.SUPERVISOR])
        self.encargado = crear_cuenta(roles=[RolSistema.ENCARGADO])
        self.ana = crear_cuenta(nombres="Ana", roles=[RolSistema.SOLICITANTE])
        self.item = crear_item("EQP-003", "Proyector")
        self.servicio = ReservaServicioAplicacion()
        self.fecha = date.today() + timedelta(days=10)

    def reserva(self, estado):
        return Reserva.objects.create(
            item_id=self.item.id, solicitante_id=self.ana.pk, fecha=self.fecha,
            hora_inicio=time(10, 0), hora_fin=time(11, 0), finalidad="Clase", estado=estado)

    def test_aprobar_como_supervisor(self):
        r = self.reserva(EstadoReserva.EN_ESPERA_SUPERVISOR)
        self.servicio.aprobar_supervisor(r.id, self.supervisor.pk)
        reg = registros(accion="APROBACION").pop()
        self.assertEqual((reg.actor_id, reg.entidad, reg.entidad_id), (self.supervisor.pk, "Reserva", r.id))

    def test_rechazar_como_supervisor_lleva_el_motivo(self):
        r = self.reserva(EstadoReserva.EN_ESPERA_SUPERVISOR)
        self.servicio.rechazar_supervisor(r.id, self.supervisor.pk, "Equipo reservado para examen")
        reg = registros(accion="RECHAZO").pop()
        self.assertEqual((reg.actor_id, reg.entidad_id), (self.supervisor.pk, r.id))
        self.assertEqual(reg.motivo, "Equipo reservado para examen")

    def test_anular_como_encargado(self):
        r = self.reserva(EstadoReserva.CONFIRMADA)
        self.servicio.anular(r.id, "El equipo entra a mantenimiento", encargado_id=self.encargado.pk)
        reg = registros(accion="CAMBIO_ESTADO").pop()
        self.assertEqual((reg.actor_id, reg.entidad, reg.entidad_id), (self.encargado.pk, "Reserva", r.id))
        self.assertIn("El equipo entra a mantenimiento", reg.motivo)

    def test_anular_desde_la_pantalla_pasa_al_encargado(self):
        r = self.reserva(EstadoReserva.CONFIRMADA)
        self.client.force_login(self.encargado)
        self.client.post(reverse("reservas:anular", args=[r.id]), {"motivo": "Cierre del laboratorio"})
        r.refresh_from_db()
        self.assertEqual(r.estado, EstadoReserva.ANULADA)
        self.assertEqual(registros(accion="CAMBIO_ESTADO").pop().actor_id, self.encargado.pk)

    def test_anular_sin_motivo_no_anula_ni_audita(self):
        r = self.reserva(EstadoReserva.CONFIRMADA)
        self.client.force_login(self.encargado)
        self.client.post(reverse("reservas:anular", args=[r.id]), {"motivo": ""})
        r.refresh_from_db()
        self.assertEqual(r.estado, EstadoReserva.CONFIRMADA)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)


class DevolucionDaniadaYReporteTests(TestCase):
    """Caso completo: se devuelve un ítem dañado -> auditoría -> aparece en el reporte."""

    def test_devolucion_daniada_queda_en_la_bitacora_y_en_el_reporte(self):
        encargado = crear_cuenta(roles=[RolSistema.ENCARGADO])
        ana = crear_cuenta(nombres="Ana", roles=[RolSistema.SOLICITANTE])
        item = crear_item("EQP-001", "Laptop")
        catalogo = CatalogoServicioAplicacion()
        catalogo.marcar_prestado(item.id)
        reserva = Reserva.objects.create(
            item_id=item.id, solicitante_id=ana.pk, fecha=date.today(), hora_inicio=time(8, 0),
            hora_fin=time(20, 0), finalidad="Clase", estado=EstadoReserva.ATENDIDA)
        prestamo = crear_prestamo(item.id, ana.pk)
        Prestamo.objects.filter(pk=prestamo.pk).update(reserva_id=reserva.id)

        prestamo_servicio().registrar_devolucion(DevolucionDTO(
            prestamo_id=prestamo.pk, encargado_id=encargado.pk,
            descripcion_condicion="Pantalla rota", garantia_devuelta=True, item_daniado=True))

        # el ítem quedó en mantenimiento y la reserva finalizada
        self.assertEqual(catalogo.obtener_item(item.id).estado, EstadoItem.MANTENIMIENTO)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.FINALIZADA)

        # auditoría: la devolución (con el encargado) y el daño del ítem
        devolucion = registros(accion="DEVOLUCION_PRESTAMO").pop()
        self.assertEqual((devolucion.actor_id, devolucion.entidad), (encargado.pk, "Prestamo"))
        dano = registros(accion="ITEM_DANIADO").pop()
        self.assertEqual((dano.entidad, dano.entidad_id, dano.motivo), ("Item", item.id, "Pantalla rota"))

        # reporte "perdidos o dañados": ahora sí cuenta el daño, con el nombre del ítem
        reporte = Reporte.objects.create(
            tipo=TipoReporte.ITEMS_PERDIDOS_DANIADOS, generado_por_id=uuid.uuid4(),
            periodo_inicio=date.today() - timedelta(days=1), periodo_fin=date.today())
        datos = reporte_servicio().generar_datos(reporte)
        self.assertEqual(dict(datos.resumen)["Ítems dañados"], "1")
        fila = next(f for f in datos.filas if f[1] == "Daño")
        self.assertEqual(fila[2], "Ítem EQP-001 · Laptop")
        self.assertEqual(fila[4], "Pantalla rota")
