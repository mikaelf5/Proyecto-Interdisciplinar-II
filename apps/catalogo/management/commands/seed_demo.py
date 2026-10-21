"""
Prepara TODO lo necesario para la demo de Catálogo, Reservas y Notificaciones.

Uso:
    python manage.py seed_demo

Crea (sin duplicar si se ejecuta dos veces):
- el catálogo de ejemplo (seed_catalogo),
- 1 encargado (staff + acceso total al admin) y 2 solicitantes, todos con contraseña "demo1234",
- EQP-001 (Laptop) y LIB-003 (DDD) como PRESTADOS,
- una cola de 2 reservas para la Laptop,
- una notificación de bienvenida para cada solicitante.

Usa los servicios de aplicación, igual que las pantallas. Las cuentas se
crean con get_user_model() (API pública de Django) para no tocar Identidad.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.catalogo.aplicacion.dtos import FiltrosItem
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import EstadoItem, TipoNotificacion
from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion

CLAVE = "demo1234"
CUENTAS = [
    # correo, nombres, dni, rol, es_staff
    ("admin@demo.pe", "Adriana Administradora", "70000000", "ADMINISTRADOR", True),
    ("encargado@demo.pe", "Elena Encargada", "70000001", "ENCARGADO", True),
    ("supervisor@demo.pe", "Sergio Supervisor", "70000004", "SUPERVISOR", True),
    ("ana@demo.pe", "Ana Alumna", "70000002", "SOLICITANTE", False),
    ("diego@demo.pe", "Diego Docente", "70000003", "SOLICITANTE", False),
]


class Command(BaseCommand):
    help = "Carga datos de demo para Catálogo, Reservas y Notificaciones."

    def _cuenta(self, correo, nombres, dni, rol, staff):
        Cuenta = get_user_model()
        cuenta = Cuenta.objects.filter(correo=correo).first()
        if not cuenta:
            cuenta = Cuenta.objects.create_user(correo, nombres, dni, CLAVE, is_staff=staff, is_superuser=staff)
        cuenta.asignar_rol(rol)  # método del dominio de Identidad (no duplica si ya lo tiene)
        return cuenta

    def handle(self, *args, **opciones):
        call_command("seed_catalogo", stdout=self.stdout)

        cuentas = [self._cuenta(*c) for c in CUENTAS]
        ana, diego = cuentas[3], cuentas[4]
        self.stdout.write(f"Cuentas listas (contraseña: {CLAVE}): " + ", ".join(c[0] for c in CUENTAS))

        catalogo = CatalogoServicioAplicacion()
        reservas = ReservaServicioAplicacion()
        notificaciones = NotificacionServicioAplicacion()

        por_codigo = {i.codigo: i for i in catalogo.buscar_items(FiltrosItem())}
        for codigo in ("EQP-001", "LIB-003"):
            item = por_codigo[codigo]
            if item.estado == EstadoItem.DISPONIBLE:
                catalogo.cambiar_estado_item(item.id, EstadoItem.PRESTADO)
        self.stdout.write("EQP-001 y LIB-003 quedaron como PRESTADOS.")

        laptop = por_codigo["EQP-001"]
        for cuenta in (ana, diego):
            try:
                r = reservas.crear(laptop.id, cuenta.id)
                self.stdout.write(f"Reserva de {cuenta.nombres}: posición {r.posicion_en_cola}")
            except ValidationError:
                pass  # ya tenía reserva (se ejecutó antes)

        for cuenta in (ana, diego):
            if not notificaciones.mis_notificaciones(cuenta.id):
                notificaciones.enviar(cuenta.id, TipoNotificacion.DISPONIBILIDAD_RESERVA,
                                      "¡Bienvenido/a! Aquí verás los avisos de tus reservas y préstamos.")

        self.stdout.write(self.style.SUCCESS("Demo lista. Entra con encargado@demo.pe / demo1234"))
