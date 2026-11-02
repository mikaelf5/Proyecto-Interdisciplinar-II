"""
Prepara TODO lo necesario para la demo.

Uso:
    python manage.py seed_demo

Crea (sin duplicar si se ejecuta dos veces):
- el catálogo de ejemplo (seed_catalogo),
- las cuentas demo (una por rol, @unsa.edu.pe, contraseña "demo1234") con sus
  perfiles, acta y consentimiento: las crea `seed_cuentas` de Identidad,
- políticas de préstamo por categoría y tipo de usuario (duración en horas),
- reservas de ejemplo para el próximo día hábil: una confirmada, una de ítem
  especial esperando al supervisor y una en lista de espera,
- una notificación de bienvenida para cada solicitante.

Usa los servicios de aplicación de cada módulo, igual que las pantallas.
"""
from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalogo.aplicacion.dtos import FiltrosItem
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import TipoNotificacion, TipoUsuario
from apps.identidad.management.commands.seed_cuentas import CLAVE_DEMO, CORREO
from apps.identidad.models import Cuenta
from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
from apps.reservas.aplicacion.dtos import NuevaReservaDTO
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
from apps.reservas.dominio.excepciones import HorarioOcupado

# Políticas: (categoría, tipo de usuario) → duración máx. (horas), renovaciones,
# antelación máx. (días), límite simultáneo global, límite simultáneo por categoría.
POLITICAS = {
    ("Libros", TipoUsuario.ALUMNO): (4, 2, 7, 2, 1),
    ("Libros", TipoUsuario.DOCENTE): (6, 2, 7, 3, 2),
    ("Libros", TipoUsuario.ADMINISTRATIVO): (4, 1, 7, 2, 1),
    ("Equipos", TipoUsuario.ALUMNO): (2, 1, 3, 2, 1),
    ("Equipos", TipoUsuario.DOCENTE): (4, 1, 7, 3, 2),
    ("Equipos", TipoUsuario.ADMINISTRATIVO): (3, 1, 3, 2, 1),
    ("Indumentaria", TipoUsuario.ALUMNO): (3, 1, 3, 2, 1),
    ("Indumentaria", TipoUsuario.DOCENTE): (4, 1, 7, 3, 2),
    ("Indumentaria", TipoUsuario.ADMINISTRATIVO): (3, 1, 3, 2, 1),
}


class Command(BaseCommand):
    help = "Carga datos de demo: catálogo, cuentas por rol, perfiles, políticas y reservas."

    def handle(self, *args, **opciones):
        call_command("seed_catalogo", stdout=self.stdout)
        call_command("seed_cuentas", stdout=self.stdout)   # cuentas demo (módulo Identidad)
        cuentas = {nombre: Cuenta.objects.get(correo=correo) for nombre, correo in CORREO.items()}

        catalogo = CatalogoServicioAplicacion()
        self._politicas(catalogo)
        self._reservas(catalogo, cuentas["ana"], cuentas["diego"])

        notificaciones = NotificacionServicioAplicacion()
        for nombre in ("ana", "diego"):
            cuenta = cuentas[nombre]
            if not notificaciones.mis_notificaciones(cuenta.id):
                notificaciones.enviar(cuenta.id, TipoNotificacion.DISPONIBILIDAD_RESERVA,
                                      "¡Bienvenido/a! Aquí verás los avisos de tus reservas y préstamos.")

        self.stdout.write(self.style.SUCCESS(
            f"Demo lista. Solicitante: {CORREO['ana']} · Encargado: {CORREO['encargado']} · "
            f"Supervisor: {CORREO['supervisor']} · Admin: {CORREO['admin']} (clave {CLAVE_DEMO})"))

    def _politicas(self, catalogo):
        from apps.politicas.aplicacion.dtos import PoliticaDTO
        from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
        from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl

        servicio = PoliticaServicioAplicacion(PoliticaRepositorioImpl())
        categorias = {c.nombre: c.id for c in catalogo.listar_categorias()}
        for (nombre, tipo), (horas, renov, antelacion, global_, por_tipo) in POLITICAS.items():
            servicio.configurar(PoliticaDTO(
                tipo_item=nombre, tipo_usuario=tipo, categoria_id=categorias[nombre],
                duracion_maxima=horas, max_renovaciones=renov, antelacion_reserva=antelacion,
                limite_simultaneo_global=global_, limite_simultaneo_por_tipo=por_tipo,
            ))
        self.stdout.write(f"Políticas configuradas: {len(POLITICAS)}")

    def _reservas(self, catalogo, ana, diego):
        reservas = ReservaServicioAplicacion()
        if reservas.mis_reservas(ana.id):
            self.stdout.write("Las reservas de ejemplo ya existían.")
            return

        dia = timezone.localdate() + timedelta(days=1)
        while not reservas.horario.atiende(dia):
            dia += timedelta(days=1)
        por_codigo = {i.codigo: i for i in catalogo.buscar_items(FiltrosItem())}

        def reservar(cuenta, codigo, desde, hasta, finalidad):
            dto = NuevaReservaDTO(solicitante_id=cuenta.id, item_id=por_codigo[codigo].id, fecha=dia,
                                  hora_inicio=desde, hora_fin=hasta, finalidad=finalidad)
            try:
                r = reservas.crear(dto)
                self.stdout.write(f"  {cuenta.nombres}: {codigo} {r.franja} → {r.estado_display}")
            except HorarioOcupado:
                r = reservas.anotarse_en_espera(dto)
                self.stdout.write(f"  {cuenta.nombres}: {codigo} {r.franja} → lista de espera n.º {r.posicion_en_cola}")
            except ValidationError as e:
                self.stdout.write(self.style.WARNING(f"  No se pudo reservar {codigo}: {' '.join(e.messages)}"))

        self.stdout.write(f"Reservas de ejemplo para el {dia:%d/%m/%Y}:")
        reservar(ana, "LIB-001", time(10, 0), time(12, 0), "Lectura para el curso de Literatura")
        reservar(ana, "EQP-001", time(14, 0), time(16, 0), "Exposición del proyecto")       # especial
        reservar(diego, "LIB-001", time(11, 0), time(13, 0), "Preparar clase")             # choca → espera
