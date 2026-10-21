from datetime import datetime

from django.test import SimpleTestCase, TestCase
from django.core.exceptions import ValidationError
from apps.politicas.dominio.models import PoliticaPrestamo
from apps.common.choices import TipoUsuario
from apps.politicas.aplicacion.dtos import PoliticaDTO
from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl


class PoliticaPrestamoTests(SimpleTestCase):

    def test_calcular_vencimiento(self):
        politica = PoliticaPrestamo(
            duracion_maxima=8
        )

        entrega = datetime(2026, 10, 21, 10, 0)

        resultado = politica.calcular_vencimiento(entrega)

        esperado = datetime(2026, 10, 21, 18, 0)

        self.assertEqual(resultado, esperado)

    def test_validar_plazo(self):
        politica = PoliticaPrestamo(
            duracion_maxima=8
        )

        entrega = datetime(2026, 10, 21, 10, 0)

        devolucion_valida = datetime(2026, 10, 21, 16, 0)
        devolucion_invalida = datetime(2026, 10, 21, 20, 0)

        self.assertTrue(
            politica.validar_plazo(entrega, devolucion_valida)
        )

        self.assertFalse(
            politica.validar_plazo(entrega, devolucion_invalida)
        )

    def test_permite_renovar(self):
        politica = PoliticaPrestamo(
            max_renovaciones=2
        )

        self.assertTrue(politica.permite_renovar(0))
        self.assertTrue(politica.permite_renovar(1))
        self.assertFalse(politica.permite_renovar(2))

class PoliticaServicioTests(TestCase):

    def test_crear_y_actualizar_politica(self):
        servicio = PoliticaServicioAplicacion(
            PoliticaRepositorioImpl()
        )

        dto = PoliticaDTO(
            tipo_item="Laptop",
            tipo_usuario=TipoUsuario.ALUMNO,
            duracion_maxima=8,
            max_renovaciones=1,
            antelacion_reserva=24,
            limite_simultaneo_global=3,
            limite_simultaneo_por_tipo=1
        )

        servicio.configurar(dto)

        politica = servicio.obtener_para(
            "Laptop",
            TipoUsuario.ALUMNO
        )

        self.assertEqual(politica.duracion_maxima, 8)

        dto.duracion_maxima = 12
        servicio.configurar(dto)

        politica = servicio.obtener_para(
            "Laptop",
            TipoUsuario.ALUMNO
        )

        self.assertEqual(politica.duracion_maxima, 12)

        self.assertEqual(
            PoliticaPrestamo.objects.filter(
                tipo_item="Laptop",
                tipo_usuario=TipoUsuario.ALUMNO
            ).count(),
            1
        )

    def test_rechazar_politica_invalida(self):
        servicio = PoliticaServicioAplicacion(
            PoliticaRepositorioImpl()
        )

        dto = PoliticaDTO(
            tipo_item="Pelota",
            tipo_usuario=TipoUsuario.ALUMNO,
            duracion_maxima=0,
            max_renovaciones=1,
            antelacion_reserva=24,
            limite_simultaneo_global=3,
            limite_simultaneo_por_tipo=1
        )

        with self.assertRaises(ValidationError):
            servicio.configurar(dto)

        self.assertFalse(
            PoliticaPrestamo.objects.filter(
                tipo_item="Pelota",
                tipo_usuario=TipoUsuario.ALUMNO
            ).exists()
        )

    def test_buscar_politica_por_categoria(self):
        import uuid

        categoria_id = uuid.uuid4()

        dto = PoliticaDTO(
            tipo_item="Laptop",
            tipo_usuario="ALUMNO",
            duracion_maxima=12,
            max_renovaciones=1,
            antelacion_reserva=0,
            limite_simultaneo_global=3,
            limite_simultaneo_por_tipo=1,
            categoria_id=categoria_id
        )

        servicio = PoliticaServicioAplicacion(PoliticaRepositorioImpl())
        servicio.configurar(dto)

        politica = servicio.obtener_por_categoria(
            categoria_id,
            "ALUMNO"
        )

        self.assertIsNotNone(politica)
        self.assertEqual(politica.categoria_id, categoria_id)

    def test_buscar_categoria_sin_politica(self):
        import uuid

        categoria_id = uuid.uuid4()

        servicio = PoliticaServicioAplicacion(PoliticaRepositorioImpl())

        politica = servicio.obtener_por_categoria(
            categoria_id,
            "ALUMNO"
        )

        self.assertIsNone(politica)

    def test_actualizar_politica_por_categoria_sin_duplicar(self):
        import uuid

        categoria_id = uuid.uuid4()

        servicio = PoliticaServicioAplicacion(
            PoliticaRepositorioImpl()
        )

        dto = PoliticaDTO(
            tipo_item="Laptop",
            tipo_usuario="ALUMNO",
            duracion_maxima=8,
            max_renovaciones=1,
            antelacion_reserva=0,
            limite_simultaneo_global=3,
            limite_simultaneo_por_tipo=1,
            categoria_id=categoria_id
        )

        servicio.configurar(dto)

        dto.duracion_maxima = 12
        servicio.configurar(dto)

        self.assertEqual(
            PoliticaPrestamo.objects.filter(
                categoria_id=categoria_id,
                tipo_usuario="ALUMNO"
            ).count(),
            1
        )

        politica = servicio.obtener_por_categoria(
            categoria_id,
            "ALUMNO"
        )

        self.assertEqual(politica.duracion_maxima, 12)