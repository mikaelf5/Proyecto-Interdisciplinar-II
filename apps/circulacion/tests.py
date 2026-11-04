import uuid
from unittest.mock import Mock, patch
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import date, timedelta, time
from django.test import TestCase
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from types import SimpleNamespace
from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl

from apps.common.choices import EstadoPrestamo, TipoGarantia, EstadoReserva
from .models import Prestamo



class PrestamoRestriccionesTest(TestCase):

    def test_no_permitir_dos_prestamos_abiertos(self):
        item_id = uuid.uuid4()
        ahora = timezone.now()

        datos = {
            "item_id": item_id,
            "solicitante_id": uuid.uuid4(),
            "reserva_id": uuid.uuid4(),
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
                        "reserva_id": uuid.uuid4(),
                    },
                    estado=EstadoPrestamo.VENCIDO
                )

    def test_permitir_prestamo_despues_de_devolucion(self):
        item_id = uuid.uuid4()
        ahora = timezone.now()

        datos = {
            "item_id": item_id,
            "solicitante_id": uuid.uuid4(),
            "reserva_id": uuid.uuid4(),
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
                "reserva_id": uuid.uuid4(),
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
            reserva_id=uuid.uuid4(),
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
            reserva_id=uuid.uuid4(),
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
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=ahora + timedelta(hours=8),
        )

        prestamo.clean()


class RepositoriosCapasTest(TestCase):

    def test_vigentes_y_vencidos(self):
        from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl
        repo = PrestamoRepositorioImpl()
        ahora = timezone.now()
        p = Prestamo.objects.create(
            item_id=uuid.uuid4(), solicitante_id=uuid.uuid4(), reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(), garantia_tipo=TipoGarantia.DNI,
            fecha_entrega=ahora-timedelta(days=2), fecha_vencimiento=ahora-timedelta(days=1))
        self.assertEqual(repo.buscar_por_id(p.id).id, p.id)
        self.assertIn(p, list(repo.vigentes_de(p.solicitante_id)))
        self.assertIn(p, list(repo.vencidos()))

class DominioExtendidoTest(TestCase):
    def crear_prestamo(self):
        ahora = timezone.now()
        return Prestamo.objects.create(
            item_id=uuid.uuid4(), solicitante_id=uuid.uuid4(), reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(), garantia_tipo=TipoGarantia.DNI,
            fecha_entrega=ahora, fecha_vencimiento=ahora+timedelta(hours=5))

    def test_renovar_respeta_limite(self):
        p = self.crear_prestamo()
        politica = Mock(
            duracion_maxima=12,
            permite_renovar=lambda n: n < 1
        )

        anterior = p.fecha_vencimiento
        nueva_fecha = anterior + timedelta(hours=12)

        p.renovar(nueva_fecha, politica)

        self.assertEqual(p.fecha_vencimiento, nueva_fecha)
        self.assertEqual(p.renovaciones_realizadas, 1)

        with self.assertRaises(ValidationError):
            p.renovar(
                nueva_fecha + timedelta(hours=12),
                politica
            )

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


class AplicacionExtendidaTest(TestCase):

    def test_entrega_rechaza_dependencias_incompletas(self):
        from apps.circulacion.aplicacion.servicios import PrestamoServicioAplicacion
        from apps.circulacion.aplicacion.dtos import EntregaPrestamoDTO
        from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl
        servicio = PrestamoServicioAplicacion(PrestamoRepositorioImpl())
        with self.assertRaises(ValidationError):
            servicio.registrar_entrega(EntregaPrestamoDTO(uuid.uuid4(), uuid.uuid4(), TipoGarantia.DNI, terminos_aceptados=True))

class RegistrarEntregaTest(TestCase):

    def test_entrega_correcta_desde_reserva_confirmada(self):
        from apps.circulacion.aplicacion.servicios import (
            PrestamoServicioAplicacion
        )
        from apps.circulacion.aplicacion.dtos import EntregaPrestamoDTO
        from apps.circulacion.infraestructura.repositorio_django import (
            PrestamoRepositorioImpl
        )

        # Identificadores de prueba.
        reserva_id = uuid.uuid4()
        item_id = uuid.uuid4()
        solicitante_id = uuid.uuid4()
        encargado_id = uuid.uuid4()
        categoria_id = uuid.uuid4()

        # Reserva confirmada para el día siguiente.
        reserva = SimpleNamespace(
            id=reserva_id,
            item_id=item_id,
            solicitante_id=solicitante_id,
            categoria_id=categoria_id,
            fecha=timezone.localdate() + timedelta(days=1),
            hora_fin=time(12, 0),
            estado=EstadoReserva.CONFIRMADA,
        )

        # Simular el servicio de Reservas.
        reservas = Mock()
        reservas.obtener.return_value = reserva

        # Simular el servicio de Catálogo.
        catalogo = Mock()
        catalogo.esta_disponible.return_value = True

        # Simular Identidad.
        identidad = Mock()
        identidad.consultar_habilitacion.return_value = SimpleNamespace(
            habilitado=True,
            mensaje=""
        )
        identidad.tipo_usuario_de.return_value = "ALUMNO"

        # Simular Políticas.
        politicas = Mock()
        politicas.politica_para.return_value = Mock()

        # Simular Auditoría.
        auditoria = Mock()

        # Construir el servicio con un repositorio real.
        servicio = PrestamoServicioAplicacion(
            prestamo_repositorio=PrestamoRepositorioImpl(),
            reservas=reservas,
            catalogo=catalogo,
            identidad=identidad,
            politica_servicio=politicas,
            auditoria=auditoria,
        )

        # Datos para registrar la entrega.
        dto = EntregaPrestamoDTO(
            reserva_id=reserva_id,
            encargado_id=encargado_id,
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            descripcion_condicion="Artículo en buen estado, sin daños visibles."
        )

        # Ejecutar la entrega.
        resultado = servicio.registrar_entrega(dto)

        # Comprobar que se creó el préstamo.
        prestamo = Prestamo.objects.get(id=resultado.id)

        self.assertEqual(prestamo.reserva_id, reserva_id)
        self.assertEqual(prestamo.item_id, item_id)
        self.assertEqual(prestamo.solicitante_id, solicitante_id)
        self.assertEqual(prestamo.estado, EstadoPrestamo.ACTIVO)

        # Comprobar la fecha de vencimiento.
        vencimiento_esperado = timezone.make_aware(
            timezone.datetime.combine(
                reserva.fecha,
                reserva.hora_fin
            ),
            timezone.get_current_timezone()
        )

        self.assertEqual(
            prestamo.fecha_vencimiento,
            vencimiento_esperado
        )

        # Comprobar las operaciones sobre los otros módulos.
        reservas.marcar_atendida.assert_called_once_with(reserva_id)
        catalogo.marcar_prestado.assert_called_once_with(item_id)

        # Comprobar el registro de la condición física.
        catalogo.registrar_condicion.assert_called_once()

        # Comprobar la auditoría.
        auditoria.registrar.assert_called_once()


class RegistrarDevolucionTest(TestCase):

    def crear_servicio_y_prestamo(self):
        from apps.circulacion.aplicacion.servicios import (
            PrestamoServicioAplicacion
        )
        from apps.circulacion.infraestructura.repositorio_django import (
            PrestamoRepositorioImpl
        )

        ahora = timezone.now()

        prestamo = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(hours=2),
            fecha_vencimiento=ahora + timedelta(hours=1),
            estado=EstadoPrestamo.ACTIVO,
        )

        catalogo = Mock()
        catalogo.obtener_item.return_value = SimpleNamespace(
            categoria_id=uuid.uuid4()
        )

        identidad = Mock()
        identidad.tipo_usuario_de.return_value = "ALUMNO"

        politicas = Mock()
        politica = Mock()
        politica.duracion_maxima = 1

        # Por defecto, no permite renovar.
        politicas.politica_para.return_value = politica
        politica.permite_renovar.return_value = False

        reservas = Mock()
        reservas.obtener.return_value = SimpleNamespace(
            fecha=prestamo.fecha_vencimiento.date(),
            hora_fin=prestamo.fecha_vencimiento.time(),
        )

        auditoria = Mock()
        notificaciones = Mock()

        servicio = PrestamoServicioAplicacion(
            prestamo_repositorio=PrestamoRepositorioImpl(),
            catalogo=catalogo,
            identidad=identidad,
            politica_servicio=politicas,
            reservas=reservas,
            auditoria=auditoria,
            notificaciones=notificaciones,
        )

        return servicio, prestamo, reservas, auditoria, ahora

    def test_devolucion_normal(self):
        from apps.circulacion.aplicacion.dtos import DevolucionDTO

        servicio, prestamo, reservas, auditoria, ahora = (
            self.crear_servicio_y_prestamo()
        )

        catalogo = servicio.catalogo
        notificaciones = servicio.notificaciones

        dto = DevolucionDTO(
            prestamo_id=prestamo.id,
            encargado_id=uuid.uuid4(),
            descripcion_condicion="Ítem devuelto en buen estado.",
            garantia_devuelta=True,
            item_daniado=False,
        )

        resultado = servicio.registrar_devolucion(dto)

        prestamo.refresh_from_db()

        self.assertEqual(prestamo.estado, EstadoPrestamo.DEVUELTO)
        self.assertTrue(prestamo.garantia_devuelta)
        self.assertIsNotNone(prestamo.fecha_devolucion_real)

        catalogo.marcar_disponible.assert_called_once_with(
            prestamo.item_id
        )
        catalogo.marcar_daniado.assert_not_called()

        reservas.liberar.assert_called_once_with(
            prestamo.reserva_id
        )

        auditoria.registrar.assert_called_once()
        notificaciones.enviar.assert_not_called()

        self.assertEqual(resultado.id, prestamo.id)

    def test_devolucion_con_danio(self):
        from apps.circulacion.aplicacion.dtos import DevolucionDTO
        from apps.common.choices import TipoNotificacion

        servicio, prestamo, reservas, auditoria, ahora = (
            self.crear_servicio_y_prestamo()
        )

        catalogo = servicio.catalogo
        notificaciones = servicio.notificaciones

        descripcion = "El equipo presenta una pantalla rota."

        dto = DevolucionDTO(
            prestamo_id=prestamo.id,
            encargado_id=uuid.uuid4(),
            descripcion_condicion=descripcion,
            garantia_devuelta=True,
            item_daniado=True,
        )

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            resultado = servicio.registrar_devolucion(dto)

        self.assertEqual(len(callbacks), 1)

        prestamo.refresh_from_db()

        self.assertEqual(prestamo.estado, EstadoPrestamo.DEVUELTO)
        self.assertTrue(prestamo.garantia_devuelta)

        catalogo.marcar_daniado.assert_called_once_with(
            prestamo.item_id,
            descripcion
        )
        catalogo.marcar_disponible.assert_not_called()

        reservas.liberar.assert_called_once_with(
            prestamo.reserva_id
        )

        auditoria.registrar.assert_called_once()

        # La notificación se registra después del commit.
        self.assertEqual(resultado.id, prestamo.id)

        from apps.common.choices import TipoNotificacion

        notificaciones.enviar.assert_called_once_with(
            prestamo.solicitante_id,
            TipoNotificacion.ITEM_DANIADO,
            f"El ítem asociado al préstamo {prestamo.id} "
            "ha sido registrado como dañado y enviado a mantenimiento."
        )

class RenovarPrestamoTest(TestCase):

    def crear_servicio_y_prestamo(self):
        from apps.circulacion.aplicacion.servicios import (
            PrestamoServicioAplicacion
        )
        from apps.circulacion.infraestructura.repositorio_django import (
            PrestamoRepositorioImpl
        )

        ahora = timezone.localtime().replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        prestamo = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=uuid.uuid4(),
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(hours=1),
            fecha_vencimiento=ahora + timedelta(hours=1),
            estado=EstadoPrestamo.ACTIVO,
        )

        catalogo = Mock()
        catalogo.obtener_item.return_value = SimpleNamespace(
            categoria_id=uuid.uuid4()
        )

        identidad = Mock()
        identidad.tipo_usuario_de.return_value = "ALUMNO"

        politica = SimpleNamespace(
            duracion_maxima=2,
            permite_renovar=Mock(return_value=False),
        )

        politicas = Mock()
        politicas.politica_para.return_value = politica

        reservas = Mock()
        reservas.obtener.return_value = SimpleNamespace(
            fecha=prestamo.fecha_vencimiento.date(),
            hora_fin=prestamo.fecha_vencimiento.time(),
        )

        auditoria = Mock()

        servicio = PrestamoServicioAplicacion(
            prestamo_repositorio=PrestamoRepositorioImpl(),
            catalogo=catalogo,
            identidad=identidad,
            politica_servicio=politicas,
            reservas=reservas,
            auditoria=auditoria,
        )

        return servicio, prestamo, reservas, auditoria, ahora

    def test_no_permitir_renovar_al_alcanzar_limite(self):
        servicio, prestamo, reservas, auditoria, ahora = (
            self.crear_servicio_y_prestamo()
        )

        with patch(
                "django.utils.timezone.now",
                return_value=ahora
        ), patch(
            "django.utils.timezone.localtime",
            return_value=ahora
        ):
            with self.assertRaisesMessage(
                    ValidationError,
                    "Se alcanzó el límite de renovaciones."
            ):
                servicio.renovar(prestamo.id, time(12, 0))

        reservas.extender.assert_not_called()
        auditoria.registrar.assert_not_called()

    def test_no_permitir_renovar_despues_de_las_20(self):
        servicio, prestamo, reservas, auditoria, ahora = (
            self.crear_servicio_y_prestamo()
        )

        # La política sí permite renovar.
        servicio.politicas.politica_para.return_value.permite_renovar.return_value = True

        hora_cierre = timezone.localtime(ahora).replace(
            hour=20, minute=0, second=0, microsecond=0
        )

        with patch(
                "django.utils.timezone.now",
                return_value=ahora
        ), patch(
            "django.utils.timezone.localtime",
            return_value=hora_cierre
        ):
            with self.assertRaisesMessage(
                    ValidationError,
                    "Las renovaciones solo se permiten antes de las 20:00."
            ):
                servicio.renovar(prestamo.id, time(12, 0))

        reservas.extender.assert_not_called()
        auditoria.registrar.assert_not_called()

    def test_no_permitir_renovar_si_la_franja_esta_ocupada(self):
        servicio, prestamo, reservas, auditoria, ahora = (
            self.crear_servicio_y_prestamo()
        )

        # La política permite renovar.
        servicio.politicas.politica_para.return_value.permite_renovar.return_value = True

        # La reserva rechaza la nueva franja.
        reservas.extender.side_effect = ValidationError(
            "La franja horaria no está disponible."
        )

        with patch(
                "django.utils.timezone.now",
                return_value=ahora
        ), patch(
            "django.utils.timezone.localtime",
            return_value=ahora
        ):
            with self.assertRaisesMessage(
                    ValidationError,
                    "La franja horaria no está disponible."
            ):
                servicio.renovar(prestamo.id, time(12, 0))

        reservas.extender.assert_called_once()
        auditoria.registrar.assert_not_called()

        prestamo.refresh_from_db()

        self.assertEqual(prestamo.renovaciones_realizadas, 0)
        self.assertEqual(
            prestamo.fecha_vencimiento,
            ahora + timedelta(hours=1)
        )

class BuscarVencidosTest(TestCase):

    def setUp(self):
        self.repositorio = PrestamoRepositorioImpl()

        self.usuario1 = uuid.uuid4()
        self.usuario2 = uuid.uuid4()

        self.item1 = uuid.uuid4()
        self.item2 = uuid.uuid4()

        ahora = timezone.now()

        # Préstamo vencido del usuario 1 y artículo 1
        self.vencido1 = Prestamo.objects.create(
            item_id=self.item1,
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=3),
            fecha_vencimiento=ahora - timedelta(days=1),
            estado=EstadoPrestamo.ACTIVO,
        )

        # Préstamo vencido del usuario 2 y artículo 2
        self.vencido2 = Prestamo.objects.create(
            item_id=self.item2,
            solicitante_id=self.usuario2,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=4),
            fecha_vencimiento=ahora - timedelta(days=2),
            estado=EstadoPrestamo.VENCIDO,
        )

        # Préstamo activo que todavía no vence
        self.no_vencido = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora,
            fecha_vencimiento=ahora + timedelta(days=2),
            estado=EstadoPrestamo.ACTIVO,
        )

        # Préstamo devuelto cuya fecha de vencimiento ya pasó
        self.devuelto = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=5),
            fecha_vencimiento=ahora - timedelta(days=2),
            fecha_devolucion_real=ahora - timedelta(days=1),
            estado=EstadoPrestamo.DEVUELTO,
        )

    def test_buscar_todos_los_vencidos(self):
        resultados = self.repositorio.buscar_vencidos()

        self.assertEqual(resultados.count(), 2)

    def test_filtrar_por_solicitante(self):
        resultados = self.repositorio.buscar_vencidos(
            solicitante_id=self.usuario1
        )

        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first().id, self.vencido1.id)

    def test_filtrar_por_item(self):
        resultados = self.repositorio.buscar_vencidos(
            item_id=self.item2
        )

        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first().id, self.vencido2.id)

    def test_excluir_no_vencidos_y_devuelto(self):
        resultados = self.repositorio.buscar_vencidos()

        ids = list(resultados.values_list("id", flat=True))

        self.assertNotIn(self.no_vencido.id, ids)
        self.assertNotIn(self.devuelto.id, ids)

class HistorialPrestamosTest(TestCase):

    def setUp(self):
        self.repositorio = PrestamoRepositorioImpl()

        self.usuario1 = uuid.uuid4()
        self.usuario2 = uuid.uuid4()

        ahora = timezone.now()

        # Préstamo activo
        self.activo = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=1),
            fecha_vencimiento=ahora + timedelta(days=2),
            estado=EstadoPrestamo.ACTIVO,
        )

        # Préstamo vencido
        self.vencido = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=5),
            fecha_vencimiento=ahora - timedelta(days=2),
            estado=EstadoPrestamo.VENCIDO,
        )

        # Préstamo devuelto
        self.devuelto = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario1,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=10),
            fecha_vencimiento=ahora - timedelta(days=7),
            fecha_devolucion_real=ahora - timedelta(days=8),
            estado=EstadoPrestamo.DEVUELTO,
        )

        # Préstamo de otro usuario
        self.otro_usuario = Prestamo.objects.create(
            item_id=uuid.uuid4(),
            solicitante_id=self.usuario2,
            reserva_id=uuid.uuid4(),
            encargado_entrega_id=uuid.uuid4(),
            garantia_tipo=TipoGarantia.DNI,
            terminos_aceptados=True,
            fecha_entrega=ahora - timedelta(days=3),
            fecha_vencimiento=ahora + timedelta(days=1),
            estado=EstadoPrestamo.ACTIVO,
        )

    def test_historial_incluye_todos_los_estados(self):
        resultados = self.repositorio.historial_de(self.usuario1)

        self.assertEqual(resultados.count(), 3)

        estados = set(resultados.values_list("estado", flat=True))

        self.assertEqual(
            estados,
            {
                EstadoPrestamo.ACTIVO,
                EstadoPrestamo.VENCIDO,
                EstadoPrestamo.DEVUELTO,
            }
        )

    def test_historial_no_incluye_otros_usuarios(self):
        resultados = self.repositorio.historial_de(self.usuario1)

        ids = list(resultados.values_list("id", flat=True))

        self.assertNotIn(self.otro_usuario.id, ids)

    def test_historial_ordenado_por_fecha_descendente(self):
        resultados = list(
            self.repositorio.historial_de(self.usuario1)
        )

        fechas = [p.fecha_entrega for p in resultados]

        self.assertEqual(fechas, sorted(fechas, reverse=True))

    def test_historial_usuario_sin_prestamos(self):
        usuario_sin_prestamos = uuid.uuid4()

        resultados = self.repositorio.historial_de(
            usuario_sin_prestamos
        )

        self.assertEqual(resultados.count(), 0)