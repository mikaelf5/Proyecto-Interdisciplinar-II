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

    def test_historial_condicion_fisica(self):
        import datetime, uuid
        from apps.catalogo.aplicacion.dtos import NuevaCondicionDTO
        prestamo, encargado = uuid.uuid4(), uuid.uuid4()
        self.s.registrar_condicion(NuevaCondicionDTO(self.laptop.id, prestamo, encargado, "ENTREGA",
                                                     datetime.date(2026, 11, 2), "Sin rayones"))
        self.s.registrar_condicion(NuevaCondicionDTO(self.laptop.id, prestamo, encargado, "DEVOLUCION",
                                                     datetime.date(2026, 11, 3), "Tecla suelta"))
        historial = self.s.historial_condicion(self.laptop.id)
        self.assertEqual([h.momento for h in historial], ["DEVOLUCION", "ENTREGA"])  # más reciente primero


class CatalogoPermisosTests(TestCase):
    """Cambiar el estado de un ítem es solo para ENCARGADO o ADMINISTRADOR."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.common.choices import RolSistema
        Cuenta = get_user_model()
        self.ana = Cuenta.objects.create_user("ana@t.pe", "Ana", "1", "x", roles=[RolSistema.SOLICITANTE])
        self.elena = Cuenta.objects.create_user("elena@t.pe", "Elena", "2", "x", roles=[RolSistema.ENCARGADO])
        s = CatalogoServicioAplicacion()
        cat = s.crear_categoria("Libros")
        self.item = s.registrar_item(NuevoItemDTO(codigo="LIB-5", categoria_id=cat.id))

    def test_solicitante_ve_el_detalle_pero_no_cambia_estados(self):
        self.client.force_login(self.ana)
        self.assertContains(self.client.get(f"/catalogo/{self.item.id}/"), "Reservar este ítem")
        r = self.client.post(f"/catalogo/{self.item.id}/daniado/", {"motivo": "x"})
        self.assertEqual(r.status_code, 403)

    def test_encargado_marca_daniado(self):
        self.client.force_login(self.elena)
        self.assertContains(self.client.get(f"/catalogo/{self.item.id}/"), "Acciones del encargado")
        self.client.post(f"/catalogo/{self.item.id}/daniado/", {"motivo": "Hojas rotas"})
        self.assertEqual(CatalogoServicioAplicacion().obtener_item(self.item.id).estado, EstadoItem.MANTENIMIENTO)


class RegistrarItemVistaTests(TestCase):
    """Pantalla 'Registrar ítem': solo ADMINISTRADOR, con campos según la categoría."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.common.choices import RolSistema
        Cuenta = get_user_model()
        self.admin = Cuenta.objects.create_user("adm@t.pe", "Adm", "1", "x", roles=[RolSistema.ADMINISTRADOR])
        self.ana = Cuenta.objects.create_user("ana@t.pe", "Ana", "2", "x", roles=[RolSistema.SOLICITANTE])
        self.cat = CatalogoServicioAplicacion().crear_categoria("Libros", definicion_atributos={
            "titulo": {"tipo": "texto", "requerido": True},
            "anio": {"tipo": "entero", "requerido": False},
        })

    def test_solo_admin(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get("/catalogo/nuevo/").status_code, 403)

    def test_registra_con_atributos_de_la_categoria(self):
        self.client.force_login(self.admin)
        r = self.client.get(f"/catalogo/nuevo/?categoria={self.cat.id}")
        self.assertContains(r, 'name="attr_titulo"')
        self.client.post("/catalogo/nuevo/", {"categoria": self.cat.id, "codigo": "lib-100",
                                              "attr_titulo": "Álgebra", "attr_anio": "2020"})
        item = CatalogoServicioAplicacion().buscar_items(FiltrosItem(texto="LIB-100"))[0]
        self.assertEqual(item.atributos, {"titulo": "Álgebra", "anio": 2020})

    def test_falta_obligatorio_muestra_error(self):
        self.client.force_login(self.admin)
        r = self.client.post("/catalogo/nuevo/", {"categoria": self.cat.id, "codigo": "LIB-101"})
        self.assertContains(r, "obligatorio")
