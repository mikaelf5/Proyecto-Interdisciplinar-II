import uuid
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import date, timedelta
from django.test import TestCase
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError

from apps.common.choices import EstadoSolicitud, EstadoPrestamo, TipoGarantia
from .models import Solicitud
from .models import Prestamo


class SolicitudTransicionesTest(SimpleTestCase):

    def test_no_aprobar_solicitud_rechazada(self):
        solicitud = Solicitud(
            estado=EstadoSolicitud.RECHAZADA
        )

        with self.assertRaises(ValidationError):
            solicitud.validar_transicion(
                EstadoSolicitud.APROBADA
            )

    def test_permitir_aprobar_solicitud_pendiente(self):
        solicitud = Solicitud(
            estado=EstadoSolicitud.PENDIENTE
        )

        solicitud.validar_transicion(
            EstadoSolicitud.APROBADA
        )


class SolicitudAprobacionTest(TestCase):

    def test_aprobar_solicitud_pendiente(self):
        revisor_id = uuid.uuid4()

        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.PENDIENTE
        )

        solicitud.aprobar(revisor_id)

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.APROBADA
        )

        self.assertEqual(
            solicitud.revisado_por_id,
            revisor_id
        )

    def test_rechazar_sin_motivo(self):
        solicitud = Solicitud(
            estado=EstadoSolicitud.PENDIENTE
        )

        with self.assertRaises(ValidationError):
            solicitud.rechazar("", uuid.uuid4())

    def test_rechazar_solicitud_pendiente(self):
        revisor_id = uuid.uuid4()

        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.PENDIENTE
        )

        solicitud.rechazar(
            "El solicitante no cumple los requisitos",
            revisor_id
        )

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.RECHAZADA
        )

        self.assertEqual(
            solicitud.motivo_rechazo,
            "El solicitante no cumple los requisitos"
        )

        self.assertEqual(
            solicitud.revisado_por_id,
            revisor_id
        )

    def test_aprobar_como_supervisor(self):
        supervisor_id = uuid.uuid4()

        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.EN_ESPERA_SUPERVISOR
        )

        solicitud.aprobar_como_supervisor(supervisor_id)

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.APROBADA
        )

        self.assertEqual(
            solicitud.aprobado_por_supervisor_id,
            supervisor_id
        )

    def test_supervisor_no_aprueba_solicitud_pendiente(self):
        solicitud = Solicitud(
            estado=EstadoSolicitud.PENDIENTE
        )

        with self.assertRaises(ValidationError):
            solicitud.aprobar_como_supervisor(
                uuid.uuid4()
            )

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.PENDIENTE
        )

    def test_cancelar_solicitud_pendiente(self):
        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.PENDIENTE
        )

        solicitud.cancelar()

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.CANCELADA
        )

    def test_no_cancelar_solicitud_aprobada(self):
        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.APROBADA
        )

        with self.assertRaises(ValidationError):
            solicitud.cancelar()

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.APROBADA
        )

    def test_rechazar_solicitud_en_espera_supervisor(self):
        revisor_id = uuid.uuid4()

        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=1),
            estado=EstadoSolicitud.EN_ESPERA_SUPERVISOR
        )

        solicitud.rechazar(
            "El supervisor no autoriza el préstamo",
            revisor_id
        )

        solicitud.refresh_from_db()

        self.assertEqual(
            solicitud.estado,
            EstadoSolicitud.RECHAZADA
        )

        self.assertEqual(
            solicitud.revisado_por_id,
            revisor_id
        )


class PrestamoRestriccionesTest(TestCase):

    def test_no_permitir_dos_prestamos_abiertos(self):
        item_id = uuid.uuid4()
        ahora = timezone.now()

        datos = {
            "item_id": item_id,
            "solicitante_id": uuid.uuid4(),
            "solicitud_id": uuid.uuid4(),
            "encargado_entrega_id": uuid.uuid4(),
            "garantia_tipo": TipoGarantia.DNI,
            "terminos_aceptados": True,
            "fecha_entrega": ahora,
            "fecha_vencimiento": ahora + timedelta(days=1),
        }

        Prestamo.objects.create(
            **datos,
            estado=EstadoPrestamo.ACTIVO
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Prestamo.objects.create(
                    **{
                        **datos,
                        "solicitud_id": uuid.uuid4(),
                    },
                    estado=EstadoPrestamo.VENCIDO
                )

    def test_permitir_prestamo_despues_de_devolucion(self):
        item_id = uuid.uuid4()
        ahora = timezone.now()

        datos = {
            "item_id": item_id,
            "solicitante_id": uuid.uuid4(),
            "solicitud_id": uuid.uuid4(),
            "encargado_entrega_id": uuid.uuid4(),
            "garantia_tipo": TipoGarantia.DNI,
            "terminos_aceptados": True,
            "fecha_entrega": ahora,
            "fecha_vencimiento": ahora + timedelta(days=1),
        }

        Prestamo.objects.create(
            **datos,
            estado=EstadoPrestamo.DEVUELTO
        )

        nuevo_prestamo = Prestamo.objects.create(
            **{
                **datos,
                "solicitante_id": uuid.uuid4(),
                "solicitud_id": uuid.uuid4(),
            },
            estado=EstadoPrestamo.ACTIVO
        )

        self.assertEqual(
            nuevo_prestamo.estado,
            EstadoPrestamo.ACTIVO
        )

        self.assertEqual(
            Prestamo.objects.filter(item_id=item_id).count(),
            2
        )

    def test_vencimiento_anterior_a_entrega(self):
        ahora = timezone.now()

        prestamo = Prestamo(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            solicitud_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=ahora - timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            prestamo.clean()

    def test_vencimiento_igual_a_entrega(self):
        ahora = timezone.now()

        prestamo = Prestamo(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            solicitud_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=ahora,
        )

        with self.assertRaises(ValidationError):
            prestamo.clean()

    def test_vencimiento_posterior_a_entrega(self):
        ahora = timezone.now()

        prestamo = Prestamo(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            solicitud_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=ahora + timedelta(hours=8),
        )

        prestamo.clean()


