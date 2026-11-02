"""
Prepara TODO lo necesario para la demo.

Uso:
    python manage.py seed_demo

Crea (sin duplicar si se ejecuta dos veces):
- el catálogo de ejemplo (seed_catalogo),
- una cuenta por rol, con sus ROLES GUARDADOS (contraseña "demo1234"),
  y solo el administrador es superusuario (así se ven los permisos por rol),
- perfiles de solicitante habilitados (acta firmada) para Ana y Diego,
- políticas de préstamo por categoría y tipo de usuario (duración en horas),
- reservas de ejemplo para el próximo día hábil: una confirmada, una de ítem
  especial esperando al supervisor y una en lista de espera,
- una notificación de bienvenida para cada solicitante.

Usa los servicios de aplicación de cada módulo, igual que las pantallas.
"""
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalogo.aplicacion.dtos import FiltrosItem
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.common.choices import RolSistema, TipoNotificacion, TipoUsuario
from apps.notificaciones.aplicacion.servicios import NotificacionServicioAplicacion
from apps.reservas.aplicacion.dtos import NuevaReservaDTO
from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
from apps.reservas.dominio.excepciones import HorarioOcupado

CLAVE = "demo1234"
CUENTAS = [
    # correo, nombres, dni, roles, es_superusuario, perfil (tipo) o None
    ("admin@demo.pe", "Adriana Administradora", "79000000", [RolSistema.ADMINISTRADOR], True, None),
    ("encargado@demo.pe", "Elena Encargada", "79000001", [RolSistema.ENCARGADO], False, None),
    ("supervisor@demo.pe", "Sergio Supervisor", "79000004", [RolSistema.SUPERVISOR], False, None),
    ("ana@demo.pe", "Ana Alumna", "79000002", [RolSistema.SOLICITANTE], False, TipoUsuario.ALUMNO),
    ("diego@demo.pe", "Diego Docente", "79000003", [RolSistema.SOLICITANTE], False, TipoUsuario.DOCENTE),
]

# Políticas: (categoría, tipo de usuario) → duración máx. (horas), renovaciones, antelación máx. (días),
#   límite global  = máximo de reservas vigentes en total (4 para todos),
#   límite por tipo = máximo de esa clase de ítem (ítems especiales: 1 a la vez).
# Duración máxima: Equipos 3 h, Libros 4 h, Indumentaria 5 h.
# Duración mínima (15 min) y anticipación mínima (30 min): reservas/dominio/horario.py.
POLITICAS = {
    ("Libros", TipoUsuario.ALUMNO): (4, 2, 7, 4, 4),
    ("Libros", TipoUsuario.DOCENTE): (4, 2, 7, 4, 4),
    ("Libros", TipoUsuario.ADMINISTRATIVO): (4, 1, 7, 4, 4),
    ("Equipos", TipoUsuario.ALUMNO): (3, 1, 3, 4, 1),
    ("Equipos", TipoUsuario.DOCENTE): (3, 1, 7, 4, 1),
    ("Equipos", TipoUsuario.ADMINISTRATIVO): (3, 1, 3, 4, 1),
    ("Indumentaria", TipoUsuario.ALUMNO): (5, 1, 3, 4, 4),
    ("Indumentaria", TipoUsuario.DOCENTE): (5, 1, 7, 4, 4),
    ("Indumentaria", TipoUsuario.ADMINISTRATIVO): (5, 1, 3, 4, 4),
}


class Command(BaseCommand):
    help = "Carga datos de demo: catálogo, cuentas por rol, perfiles, políticas y reservas."

    def handle(self, *args, **opciones):
        call_command("seed_catalogo", stdout=self.stdout)
        cuentas = {c[0]: self._cuenta(*c) for c in CUENTAS}
        self.stdout.write(f"Cuentas listas (contraseña: {CLAVE}): " + ", ".join(cuentas))

        catalogo = CatalogoServicioAplicacion()
        self._politicas(catalogo)
        self._reservas(catalogo, cuentas["ana@demo.pe"], cuentas["diego@demo.pe"])

        notificaciones = NotificacionServicioAplicacion()
        for correo in ("ana@demo.pe", "diego@demo.pe"):
            cuenta = cuentas[correo]
            if not notificaciones.mis_notificaciones(cuenta.id):
                notificaciones.enviar(cuenta.id, TipoNotificacion.DISPONIBILIDAD_RESERVA,
                                      "¡Bienvenido/a! Aquí verás los avisos de tus reservas y préstamos.")

        self.stdout.write(self.style.SUCCESS(
            "Demo lista. Solicitante: ana@demo.pe · Encargado: encargado@demo.pe · "
            "Supervisor: supervisor@demo.pe · Admin: admin@demo.pe (clave demo1234)"))

    def _cuenta(self, correo, nombres, dni, roles, es_super, tipo_perfil):
        Cuenta = get_user_model()
        cuenta = Cuenta.objects.filter(correo=correo).first()
        if not cuenta:
            # Si ese DNI ya lo usa otra cuenta (p. ej. de crear_cuentas_prueba.py),
            # se busca el siguiente DNI libre para no chocar con la restricción UNIQUE.
            while Cuenta.objects.filter(dni=dni).exists():
                dni = str(int(dni) + 100)
            crear = Cuenta.objects.create_superuser if es_super else Cuenta.objects.create_user
            cuenta = crear(correo, nombres, dni, CLAVE)
        cuenta.roles = []
        for rol in roles:
            cuenta.asignar_rol(rol)          # regla del dominio de Identidad…
        cuenta.is_staff = es_super or RolSistema.SOLICITANTE not in roles  # personal entra al admin
        cuenta.is_superuser = es_super       # solo el admin; así se notan los permisos por rol
        cuenta.save()                        # …y AQUÍ se guarda (antes faltaba este save)

        if tipo_perfil:
            from apps.identidad.models import PerfilSolicitante
            PerfilSolicitante.objects.update_or_create(cuenta=cuenta, defaults=dict(
                tipo=tipo_perfil, habilitado_institucional=True,
                acta_version="v1", acta_fecha_firma=timezone.localdate(),
            ))
        return cuenta

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
