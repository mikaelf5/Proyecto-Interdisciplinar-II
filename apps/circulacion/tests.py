import uuid
from unittest.mock import Mock
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import date, timedelta
from django.test import TestCase
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from apps.circulacion.services import ServicioDeAprobacion

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

class ServicioDeAprobacionTests(TestCase):

    def test_item_especial_requiere_supervisor(self):
        # Simulamos el servicio de Catálogo
        catalogo = Mock()
        catalogo.es_especial.return_value = True

        # Simulamos una solicitud pendiente
        solicitud = Mock()
        solicitud.estado = EstadoSolicitud.PENDIENTE
        solicitud.item_id = "item-123"
        solicitud.categoria_id = None

        servicio = ServicioDeAprobacion(catalogo)

        resultado = servicio.determinar_flujo(solicitud)

        self.assertEqual(
            resultado,
            EstadoSolicitud.EN_ESPERA_SUPERVISOR
        )

        solicitud.validar_transicion.assert_called_once_with(
            EstadoSolicitud.EN_ESPERA_SUPERVISOR
        )

        solicitud.save.assert_called_once()

    def test_item_normal_no_requiere_supervisor(self):
        # Simulamos un ítem normal
        catalogo = Mock()
        catalogo.es_especial.return_value = False

        # Simulamos una solicitud pendiente
        solicitud = Mock()
        solicitud.estado = EstadoSolicitud.PENDIENTE
        solicitud.item_id = "item-123"
        solicitud.categoria_id = None

        servicio = ServicioDeAprobacion(catalogo)

        resultado = servicio.determinar_flujo(solicitud)

        self.assertEqual(
            resultado,
            EstadoSolicitud.PENDIENTE
        )

        solicitud.validar_transicion.assert_not_called()
        solicitud.save.assert_not_called()

    def test_no_permite_procesar_solicitud_aprobada(self):
        catalogo = Mock()

        solicitud = Mock()
        solicitud.estado = EstadoSolicitud.APROBADA

        servicio = ServicioDeAprobacion(catalogo)

        with self.assertRaises(ValidationError):
            servicio.determinar_flujo(solicitud)

        catalogo.es_especial.assert_not_called()
        solicitud.save.assert_not_called()

    def test_categoria_especial_requiere_supervisor(self):
        catalogo = Mock()
        catalogo.es_especial.return_value = True

        solicitud = Mock()
        solicitud.estado = EstadoSolicitud.PENDIENTE
        solicitud.item_id = None
        solicitud.categoria_id = "categoria-123"

        servicio = ServicioDeAprobacion(catalogo)

        resultado = servicio.determinar_flujo(solicitud)

        catalogo.es_especial.assert_called_once_with(
            item_id=None,
            categoria_id="categoria-123"
        )

        self.assertEqual(
            resultado,
            EstadoSolicitud.EN_ESPERA_SUPERVISOR
        )

        solicitud.save.assert_called_once()

class RepositoriosCapasTest(TestCase):
    def test_solicitudes_pendientes_y_buscar_por_id(self):
        from apps.circulacion.infraestructura.repositorio_django import SolicitudRepositorioImpl
        repo = SolicitudRepositorioImpl()
        solicitud = Solicitud.objects.create(
            item_id=uuid.uuid4(), solicitante_id=uuid.uuid4(),
            fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=1))
        self.assertEqual(repo.buscar_por_id(solicitud.id).id, solicitud.id)
        self.assertIn(solicitud, list(repo.pendientes()))

    def test_vigentes_y_vencidos(self):
        from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl
        repo = PrestamoRepositorioImpl()
        ahora = timezone.now()
        p = Prestamo.objects.create(
            item_id=uuid.uuid4(), solicitante_id=uuid.uuid4(), solicitud_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(), garantia_tipo=TipoGarantia.DNI,
            fecha_entrega=ahora-timedelta(days=2), fecha_vencimiento=ahora-timedelta(days=1))
        self.assertEqual(repo.buscar_por_id(p.id).id, p.id)
        self.assertIn(p, list(repo.vigentes_de(p.solicitante_id)))
        self.assertIn(p, list(repo.vencidos()))

class DominioExtendidoTest(TestCase):
    def crear_prestamo(self):
        ahora = timezone.now()
        return Prestamo.objects.create(
            item_id=uuid.uuid4(), solicitante_id=uuid.uuid4(), solicitud_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(), garantia_tipo=TipoGarantia.DNI,
            fecha_entrega=ahora, fecha_vencimiento=ahora+timedelta(hours=5))

    def test_renovar_respeta_limite(self):
        p = self.crear_prestamo()
        politica = Mock(duracion_maxima=12, permite_renovar=lambda n: n < 1)
        anterior = p.fecha_vencimiento
        p.renovar(politica)
        self.assertEqual(p.fecha_vencimiento, anterior + timedelta(hours=12))
        self.assertEqual(p.renovaciones_realizadas, 1)
        with self.assertRaises(ValidationError):
            p.renovar(politica)

    def test_devolver_y_no_devolver_dos_veces(self):
        p = self.crear_prestamo()
        encargado = uuid.uuid4()
        p.registrar_devolucion(encargado_id=encargado)
        self.assertEqual(p.estado, EstadoPrestamo.DEVUELTO)
        self.assertEqual(p.encargado_devolucion_id, encargado)
        with self.assertRaises(ValidationError):
            p.registrar_devolucion(encargado_id=encargado)

    def test_cerrar_por_perdida(self):
        p = self.crear_prestamo()
        p.cerrar_por_perdida()
        self.assertEqual(p.estado, EstadoPrestamo.CERRADO_POR_PERDIDA)
        with self.assertRaises(ValidationError):
            p.cerrar_por_perdida()

    def test_elegibilidad_regla_pura(self):
        from apps.circulacion.dominio.servicios import ServicioDeElegibilidad
        politica = Mock(limite_simultaneo_global=2)
        perfil = Mock(habilitado=True)
        self.assertTrue(ServicioDeElegibilidad().evaluar(perfil, False, politica, [1]))
        self.assertFalse(ServicioDeElegibilidad().evaluar(perfil, True, politica, []))
        self.assertFalse(ServicioDeElegibilidad().evaluar(perfil, False, politica, [1, 2]))

    def test_decidir_supervisor(self):
        from apps.circulacion.dominio.servicios import ServicioDeAprobacion
        servicio = ServicioDeAprobacion(Mock())
        solicitud = Solicitud(estado=EstadoSolicitud.PENDIENTE)
        self.assertEqual(servicio.decidir(solicitud, True), EstadoSolicitud.EN_ESPERA_SUPERVISOR)
        self.assertEqual(servicio.decidir(solicitud, False), EstadoSolicitud.APROBADA)

class AplicacionExtendidaTest(TestCase):
    def test_solicitar_aprobar_rechazar_cancelar(self):
        from apps.circulacion.aplicacion.servicios import SolicitudServicioAplicacion
        from apps.circulacion.aplicacion.dtos import SolicitudDTO
        from apps.circulacion.infraestructura.repositorio_django import SolicitudRepositorioImpl
        servicio = SolicitudServicioAplicacion(SolicitudRepositorioImpl())
        def crear():
            return servicio.solicitar(SolicitudDTO(uuid.uuid4(), None, uuid.uuid4(),
                date.today(), date.today()+timedelta(days=1)))
        encargado = uuid.uuid4()
        s = crear()
        servicio.aprobar(s.id, encargado)
        s.refresh_from_db()
        self.assertEqual(s.estado, EstadoSolicitud.APROBADA)
        s = crear()
        servicio.rechazar(s.id, encargado, "No cumple")
        s.refresh_from_db()
        self.assertEqual(s.estado, EstadoSolicitud.RECHAZADA)
        s = crear()
        servicio.cancelar(s.id)
        s.refresh_from_db()
        self.assertEqual(s.estado, EstadoSolicitud.CANCELADA)

    def test_entrega_rechaza_dependencias_incompletas(self):
        from apps.circulacion.aplicacion.servicios import PrestamoServicioAplicacion
        from apps.circulacion.aplicacion.dtos import EntregaPrestamoDTO
        from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl
        servicio = PrestamoServicioAplicacion(PrestamoRepositorioImpl())
        with self.assertRaises(ValidationError):
            servicio.registrar_entrega(EntregaPrestamoDTO(uuid.uuid4(), uuid.uuid4(), TipoGarantia.DNI, terminos_aceptados=True))
