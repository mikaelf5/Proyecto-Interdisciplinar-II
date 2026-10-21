from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.catalogo.aplicacion.dtos import FiltrosItem, NuevoItemDTO
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import EstadoItem


class CatalogoServicioTests(TestCase):
    def setUp(self):
        self.s = CatalogoServicioAplicacion()
        self.equipos = self.s.crear_categoria(
            "Equipos", es_especial=True,
            definicion_atributos={"nombre": {"tipo": "texto", "requerido": True},
                                  "numero_serie": {"tipo": "texto", "requerido": True}},
        )
        self.laptop = self.s.registrar_item(NuevoItemDTO(
            codigo="EQP-001", categoria_id=self.equipos.id,
            atributos={"nombre": "Laptop", "numero_serie": "LNV-1"},
        ))

    def test_registrar_item_sin_atributo_obligatorio_falla(self):
        with self.assertRaises(ValidationError):
            self.s.registrar_item(NuevoItemDTO(codigo="EQP-002", categoria_id=self.equipos.id,
                                               atributos={"nombre": "Proyector"}))

    def test_codigo_duplicado_falla(self):
        with self.assertRaises(ValidationError):
            self.s.registrar_item(NuevoItemDTO(codigo="EQP-001", categoria_id=self.equipos.id,
                                               atributos={"nombre": "Otra", "numero_serie": "Z"}))

    def test_maquina_de_estados(self):
        dto = self.s.marcar_daniado(self.laptop.id, "Pantalla rota")
        self.assertEqual(dto.estado, EstadoItem.MANTENIMIENTO)
        self.assertEqual(dto.motivo_fuera_servicio, "Pantalla rota")
        dto = self.s.cambiar_estado_item(self.laptop.id, EstadoItem.DISPONIBLE)
        self.assertEqual(dto.motivo_fuera_servicio, "")

    def test_item_de_baja_no_se_reactiva(self):
        self.s.dar_de_baja_item(self.laptop.id, "Obsoleto")
        with self.assertRaises(ValidationError):
            self.s.cambiar_estado_item(self.laptop.id, EstadoItem.DISPONIBLE)

    def test_marcar_daniado_exige_motivo(self):
        with self.assertRaises(ValidationError):
            self.s.marcar_daniado(self.laptop.id, "   ")

    def test_buscar_por_texto_en_atributos(self):
        self.assertEqual(len(self.s.buscar_items(FiltrosItem(texto="laptop"))), 1)
        self.assertEqual(len(self.s.buscar_items(FiltrosItem(texto="cámara"))), 0)

    def test_es_especial_para_circulacion(self):
        self.assertTrue(self.s.es_especial(item_id=self.laptop.id))
        self.assertTrue(self.s.es_especial(categoria_id=self.equipos.id))

    def test_marcar_prestado_y_disponible(self):
        self.assertEqual(self.s.marcar_prestado(self.laptop.id).estado, EstadoItem.PRESTADO)
        self.assertEqual(self.s.marcar_disponible(self.laptop.id).estado, EstadoItem.DISPONIBLE)

    def test_no_se_presta_un_item_en_mantenimiento(self):
        self.s.marcar_daniado(self.laptop.id, "Pantalla rota")
        with self.assertRaises(ValidationError):
            self.s.marcar_prestado(self.laptop.id)
