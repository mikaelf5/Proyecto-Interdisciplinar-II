"""
Pruebas de Reservas.

Se usa un RELOJ FIJO (lunes 02/11/2026 a las 09:00, hora de Lima) para que las
pruebas den siempre el mismo resultado sin importar el día en que se ejecuten.
Identidad y Políticas se reemplazan por versiones falsas en las pruebas del
servicio; al final hay pruebas de integración con los módulos reales.
"""
import uuid
from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.auditoria.models import RegistroAuditoria
from apps.catalogo.aplicacion.dtos import NuevoItemDTO
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import EstadoReserva, RolSistema, TipoUsuario
from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
from apps.reservas.aplicacion.dtos import NuevaReservaDTO
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
from apps.reservas.dominio.excepciones import HorarioOcupado
from apps.reservas.dominio.horario import HorarioAtencion
from apps.reservas.dominio.servicios import AsignadorDeCola, CalculadoraDeHorarios, ReglasDeReserva

LIMA = ZoneInfo("America/Lima")
LUNES = date(2026, 11, 2)
AHORA = datetime(2026, 11, 2, 9, 0, tzinfo=LIMA)


def h(texto):
    return time.fromisoformat(texto)


def politica(**cambios):
    datos = dict(duracion_maxima=4, antelacion_reserva=7, limite_simultaneo_global=5,
                 limite_simultaneo_por_tipo=5, max_renovaciones=1)
    datos.update(cambios)
    return SimpleNamespace(**datos)


class IdentidadFalsa:
    def __init__(self):
        self.bloqueados = set()

    def habilitacion(self, cuenta_id):
        if cuenta_id in self.bloqueados:
            return False, "Tiene una sanción vigente."
        return True, "Habilitado."

    def tipo_usuario(self, cuenta_id):
        return TipoUsuario.ALUMNO


class PoliticasFalsas:
    def __init__(self, valor=None):
        self.valor = valor or politica()

    def politica_para(self, categoria_id, tipo_usuario):
        return self.valor


class _R:
    def __init__(self, pos=None, estado="ACTIVA", desde="10:00", hasta="12:00"):
        self.posicion_en_cola, self.estado = pos, estado
        self.hora_inicio, self.hora_fin = h(desde), h(hasta)


class DominioTests(SimpleTestCase):
    def test_siguiente_es_el_primero_activo(self):
        cola = [_R(3), _R(1, "CANCELADA"), _R(2)]
        self.assertEqual(AsignadorDeCola.siguiente(cola).posicion_en_cola, 2)

    def test_nueva_va_al_final(self):
        self.assertEqual(AsignadorDeCola.posicion_para_nueva([_R(1), _R(2)]), 3)
        self.assertEqual(AsignadorDeCola.posicion_para_nueva([]), 1)

    def test_horarios_libres_del_dia(self):
        calc = CalculadoraDeHorarios(HorarioAtencion())
        libres = calc.libres(LUNES, [_R(desde="10:00", hasta="12:00"), _R(desde="14:00", hasta="15:00")], AHORA)
        self.assertEqual(libres, [(h("09:00"), h("10:00")), (h("12:00"), h("14:00")), (h("15:00"), h("20:00"))])

    def test_reglas_horario_duracion_antelacion(self):
        reglas = ReglasDeReserva(HorarioAtencion())
        reglas.validar(LUNES, h("10:00"), h("12:00"), AHORA, politica())          # válida
        casos = [
            (date(2026, 11, 7), h("10:00"), h("11:00")),   # sábado: no hay atención
            (LUNES, h("19:00"), h("21:00")),                # pasa del cierre
            (LUNES, h("08:00"), h("08:30")),                # ya pasó (son las 9:00)
            (LUNES, h("10:00"), h("15:00")),                # 5 h > 4 h de la política
            (date(2026, 11, 13), h("10:00"), h("11:00")),   # 11 días > 7 de antelación
        ]
        for fecha, desde, hasta in casos:
            with self.subTest(fecha=fecha, desde=desde), self.assertRaises(ValidationError):
                reglas.validar(fecha, desde, hasta, AHORA, politica())


class ReservaServicioTests(TestCase):
    def setUp(self):
        catalogo = CatalogoServicioAplicacion()
        libros = catalogo.crear_categoria("Libros")
        equipos = catalogo.crear_categoria("Equipos", es_especial=True)
        self.libro = catalogo.registrar_item(NuevoItemDTO(codigo="LIB-1", categoria_id=libros.id))
        self.libro2 = catalogo.registrar_item(NuevoItemDTO(codigo="LIB-2", categoria_id=libros.id))
        self.laptop = catalogo.registrar_item(NuevoItemDTO(codigo="EQP-1", categoria_id=equipos.id))
        self.libros = libros
        self.identidad = IdentidadFalsa()
        self.politicas = PoliticasFalsas()
        self.reloj = lambda: AHORA
        self.s = ReservaServicioAplicacion(identidad=self.identidad, politicas=self.politicas, reloj=self.reloj)
        self.ana, self.beto, self.caro = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.supervisor, self.encargado = uuid.uuid4(), uuid.uuid4()

    def dto(self, quien, desde="10:00", hasta="12:00", item=None, fecha=LUNES, categoria=None):
        item_id = None if categoria else (item or self.libro).id
        return NuevaReservaDTO(solicitante_id=quien, fecha=fecha, hora_inicio=h(desde), hora_fin=h(hasta),
                               item_id=item_id, categoria_id=categoria)

    def avisos(self, cuenta):
        return NotificacionServicioAplicacion().mis_notificaciones(cuenta)

    # ---- aprobación automática
    def test_item_normal_se_confirma_solo(self):
        self.assertEqual(self.s.crear(self.dto(self.ana)).estado, EstadoReserva.CONFIRMADA)

    def test_item_especial_va_al_supervisor(self):
        r = self.s.crear(self.dto(self.ana, item=self.laptop))
        self.assertEqual(r.estado, EstadoReserva.EN_ESPERA_SUPERVISOR)

    # ---- franja exclusiva
    def test_franja_exclusiva_rechaza_con_alternativas(self):
        self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        with self.assertRaises(HorarioOcupado) as ctx:
            self.s.crear(self.dto(self.beto, "11:00", "13:00"))
        error = ctx.exception
        self.assertIn("ya está reservado", error.messages[0])
        self.assertIn((h("12:00"), h("20:00")), error.horarios_libres)
        self.assertEqual([i.codigo for i in error.alternativos], ["LIB-2"])

    def test_franjas_seguidas_si_se_permiten(self):
        self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        self.assertEqual(self.s.crear(self.dto(self.beto, "12:00", "13:00")).estado, EstadoReserva.CONFIRMADA)

    def test_reservar_por_categoria_asigna_un_item_libre(self):
        self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        r = self.s.crear(self.dto(self.beto, "10:00", "12:00", categoria=self.libros.id))
        self.assertEqual(r.item_id, self.libro2.id)

    # ---- lista de espera FIFO
    def test_lista_espera_fifo_y_aviso_al_liberarse(self):
        primera = self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        beto = self.s.anotarse_en_espera(self.dto(self.beto, "10:00", "12:00"))
        caro = self.s.anotarse_en_espera(self.dto(self.caro, "10:00", "12:00"))
        self.assertEqual((beto.posicion_en_cola, caro.posicion_en_cola), (1, 2))

        self.s.cancelar(primera.id, self.ana)

        self.assertEqual(self.s.obtener(beto.id).estado, EstadoReserva.CONFIRMADA)   # el primero de la fila
        self.assertEqual(self.s.obtener(caro.id).estado, EstadoReserva.ACTIVA)       # sigue esperando
        self.assertEqual(len(self.avisos(self.beto)), 1)
        self.assertIn("quedó reservado para ti", self.avisos(self.beto)[0].mensaje)

    def test_no_se_anota_en_espera_si_el_horario_esta_libre(self):
        with self.assertRaises(ValidationError):
            self.s.anotarse_en_espera(self.dto(self.beto))

    def test_solo_el_dueno_cancela(self):
        r = self.s.crear(self.dto(self.ana))
        with self.assertRaises(ValidationError):
            self.s.cancelar(r.id, self.beto)

    # ---- supervisor
    def test_supervisor_aprueba_pero_no_su_propia_reserva(self):
        r = self.s.crear(self.dto(self.ana, item=self.laptop))
        propia = self.s.crear(self.dto(self.supervisor, "14:00", "15:00", item=self.laptop))
        with self.assertRaises(ValidationError):
            self.s.aprobar_supervisor(propia.id, self.supervisor)
        self.assertEqual(self.s.aprobar_supervisor(r.id, self.supervisor).estado, EstadoReserva.CONFIRMADA)
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="Reserva", entidad_id=r.id).exists())

    def test_rechazo_del_supervisor_exige_motivo_y_libera_la_franja(self):
        r = self.s.crear(self.dto(self.ana, item=self.laptop))
        espera = self.s.anotarse_en_espera(self.dto(self.beto, item=self.laptop))
        with self.assertRaises(ValidationError):
            self.s.rechazar_supervisor(r.id, self.supervisor, "  ")
        self.s.rechazar_supervisor(r.id, self.supervisor, "Equipo reservado para mantenimiento")
        self.assertEqual(self.s.obtener(r.id).estado, EstadoReserva.RECHAZADA)
        self.assertEqual(self.s.obtener(espera.id).estado, EstadoReserva.EN_ESPERA_SUPERVISOR)

    # ---- encargado
    def test_anular_exige_motivo_y_queda_en_auditoria(self):
        r = self.s.crear(self.dto(self.ana))
        with self.assertRaises(ValidationError):
            self.s.anular(r.id, self.encargado, "")
        self.s.anular(r.id, self.encargado, "El libro se mojó")
        self.assertEqual(self.s.obtener(r.id).estado, EstadoReserva.ANULADA)
        registro = RegistroAuditoria.objects.get(entidad="Reserva", entidad_id=r.id)
        self.assertIn("El libro se mojó", registro.motivo)

    # ---- expiración
    def test_expira_si_no_la_recoge_en_15_minutos_y_avanza_la_cola(self):
        r = self.s.crear(self.dto(self.ana, "09:30", "10:30"))
        espera = self.s.anotarse_en_espera(self.dto(self.beto, "10:00", "11:00"))
        self.s.expirar_reservas(datetime(2026, 11, 2, 9, 40, tzinfo=LIMA))     # 10 min: aún no
        self.assertEqual(self.s.obtener(r.id).estado, EstadoReserva.CONFIRMADA)
        self.s.expirar_reservas(datetime(2026, 11, 2, 9, 46, tzinfo=LIMA))     # 16 min: expira
        self.assertEqual(self.s.obtener(r.id).estado, EstadoReserva.EXPIRADA)
        self.assertEqual(self.s.obtener(espera.id).estado, EstadoReserva.CONFIRMADA)

    # ---- reglas con Identidad y Políticas
    def test_usuario_no_habilitado_no_reserva(self):
        self.identidad.bloqueados.add(self.ana)
        with self.assertRaisesMessage(ValidationError, "No estás habilitado"):
            self.s.crear(self.dto(self.ana))

    def test_sin_politica_no_reserva(self):
        self.politicas.valor = None
        with self.assertRaisesMessage(ValidationError, "No hay una política"):
            self.s.crear(self.dto(self.ana))

    def test_limite_de_reservas_simultaneas(self):
        self.politicas.valor = politica(limite_simultaneo_global=1)
        self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        with self.assertRaisesMessage(ValidationError, "máximo es 1 a la vez"):
            self.s.crear(self.dto(self.ana, "11:00", "12:00", item=self.libro2))
        self.s.crear(self.dto(self.ana, "13:00", "14:00", item=self.libro2))   # otro horario: sí

    # ---- contrato con Préstamos
    def test_contrato_prestamos_entregar_renovar_devolver(self):
        r = self.s.crear(self.dto(self.ana, "10:00", "12:00"))
        self.s.crear(self.dto(self.beto, "13:00", "14:00"))
        self.assertEqual([x.id for x in self.s.confirmadas_de_hoy()], [r.id, self.s.mis_reservas(self.beto)[0].id])

        self.assertEqual(self.s.marcar_atendida(r.id).estado, EstadoReserva.ATENDIDA)
        self.assertFalse(self.s.franja_libre(self.libro.id, LUNES, h("11:00"), h("11:30")))  # sigue ocupado

        self.assertEqual(self.s.extender(r.id, h("13:00")).hora_fin, h("13:00"))   # renovar hasta 13:00
        with self.assertRaisesMessage(ValidationError, "ya está reservada"):
            self.s.extender(r.id, h("13:30"))                                     # choca con Beto
        with self.assertRaises(ValidationError):
            self.s.extender(r.id, h("20:30"))                                     # pasa del cierre

        self.assertEqual(self.s.liberar(r.id).estado, EstadoReserva.FINALIZADA)


class IntegracionTests(TestCase):
    """Con Identidad y Políticas REALES (perfil del solicitante + política en la base)."""

    def setUp(self):
        from apps.identidad.models import PerfilSolicitante
        from apps.politicas.aplicacion.dtos import PoliticaDTO
        from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
        from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl

        catalogo = CatalogoServicioAplicacion()
        cat = catalogo.crear_categoria("Libros")
        self.libro = catalogo.registrar_item(NuevoItemDTO(codigo="LIB-9", categoria_id=cat.id))
        PoliticaServicioAplicacion(PoliticaRepositorioImpl()).configurar(PoliticaDTO(
            tipo_item="Libros", tipo_usuario=TipoUsuario.ALUMNO, categoria_id=cat.id, duracion_maxima=4,
            max_renovaciones=1, antelacion_reserva=7, limite_simultaneo_global=2, limite_simultaneo_por_tipo=1,
        ))
        Cuenta = get_user_model()
        self.ana = Cuenta.objects.create_user("ana@t.pe", "Ana", "1", "x", roles=[RolSistema.SOLICITANTE])
        self.sin_perfil = Cuenta.objects.create_user("sp@t.pe", "Sin Perfil", "2", "x")
        PerfilSolicitante.objects.create(cuenta=self.ana, tipo=TipoUsuario.ALUMNO, habilitado_institucional=True,
                                         acta_version="v1", acta_fecha_firma=LUNES)
        self.s = ReservaServicioAplicacion(reloj=lambda: AHORA)

    def test_reserva_con_modulos_reales(self):
        r = self.s.crear(NuevaReservaDTO(self.ana.id, LUNES, h("10:00"), h("12:00"), item_id=self.libro.id))
        self.assertEqual(r.estado, EstadoReserva.CONFIRMADA)

    def test_cuenta_sin_perfil_no_esta_habilitada(self):
        with self.assertRaisesMessage(ValidationError, "No estás habilitado"):
            self.s.crear(NuevaReservaDTO(self.sin_perfil.id, LUNES, h("10:00"), h("11:00"), item_id=self.libro.id))


class VistasTests(TestCase):
    """Permisos por rol en las pantallas."""

    def setUp(self):
        Cuenta = get_user_model()
        self.ana = Cuenta.objects.create_user("ana@t.pe", "Ana", "1", "x", roles=[RolSistema.SOLICITANTE])
        self.sup = Cuenta.objects.create_user("sup@t.pe", "Sergio", "2", "x", roles=[RolSistema.SUPERVISOR])
        cat = CatalogoServicioAplicacion().crear_categoria("Libros")
        self.libro = CatalogoServicioAplicacion().registrar_item(NuevoItemDTO(codigo="LIB-7", categoria_id=cat.id))

    def test_bandeja_solo_para_supervisor(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get("/reservas/supervisor/").status_code, 403)
        self.client.force_login(self.sup)
        self.assertEqual(self.client.get("/reservas/supervisor/").status_code, 200)

    def test_solicitante_ve_formulario_y_agenda(self):
        self.client.force_login(self.ana)
        self.assertContains(self.client.get(f"/reservas/item/{self.libro.id}/reservar/"), "Reservar")
        self.assertContains(self.client.get(f"/reservas/item/{self.libro.id}/agenda/"), "Agenda")
        self.assertContains(self.client.get("/reservas/mias/"), "Mis reservas")

    def test_supervisor_no_puede_reservar(self):
        self.client.force_login(self.sup)
        self.assertEqual(self.client.get(f"/reservas/item/{self.libro.id}/reservar/").status_code, 403)
