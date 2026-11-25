"""
Datos de la revisión y de la entrega final.

Uso:
    python manage.py seed_entrega

Se puede correr varias veces: no duplica nada.

1. Cuentas: corre `seed_unsa` (alumnos, docentes y administrativos del curso, con
   el personal: administrador, encargado y supervisor). Clave de todos: unsa2026.
2. Catálogo: 20 ítems en Libros, Equipos (categoría especial: la aprueba el
   supervisor) e Indumentaria, con todos sus atributos.
3. Políticas de préstamo por categoría y tipo de usuario.
4. Préstamos:
   - 5 ACTIVOS de hoy: ítem PRESTADO, reserva ATENDIDA, garantía y condición física.
   - Préstamos DEVUELTOS de días anteriores (algunos con atraso y una sanción) para
     que los reportes y los historiales tengan datos.

Un préstamo dura un solo día y dentro del horario de atención (lunes a viernes de
08:00 a 20:00). Por eso los 5 activos se crean para HOY y solo en horario de atención:
hay que correr el comando el mismo día de la revisión. Si se corre otro día, cierra
los activos de días anteriores (como devueltos) y crea los de hoy.
"""
from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalogo.management.commands.seed_catalogo import CATEGORIAS
from apps.catalogo.management.commands.seed_demo import POLITICAS
from apps.catalogo.models import Categoria, CondicionFisica, Item
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import (
    EstadoItem, EstadoPrestamo, EstadoReserva, RolSistema, TipoGarantia, TipoUsuario,
)
from apps.identidad.models import Cuenta, PerfilSolicitante
from apps.reservas.dominio.horario import HorarioAtencion
from apps.reservas.dominio.models import Reserva
from apps.sanciones.dominio.models import Sancion, TipoSancion

# código, categoría, atributos (todos los de su categoría)
ITEMS = [
    ("LIB-001", "Libros", {"titulo": "Cien años de soledad", "autor": "Gabriel García Márquez",
                           "isbn": "9780307474728", "editorial": "Sudamericana", "anio": 1967}),
    ("LIB-002", "Libros", {"titulo": "Clean Code", "autor": "Robert C. Martin",
                           "isbn": "9780132350884", "editorial": "Prentice Hall", "anio": 2008}),
    ("LIB-003", "Libros", {"titulo": "Domain-Driven Design", "autor": "Eric Evans",
                           "isbn": "9780321125217", "editorial": "Addison-Wesley", "anio": 2003}),
    ("LIB-004", "Libros", {"titulo": "Cálculo de una variable", "autor": "James Stewart",
                           "isbn": "9786075228143", "editorial": "Cengage", "anio": 2018}),
    ("LIB-005", "Libros", {"titulo": "Introducción a los algoritmos", "autor": "Thomas H. Cormen",
                           "isbn": "9780262046305", "editorial": "MIT Press", "anio": 2022}),
    ("LIB-006", "Libros", {"titulo": "Sistemas operativos modernos", "autor": "Andrew S. Tanenbaum",
                           "isbn": "9786073237376", "editorial": "Pearson", "anio": 2015}),
    ("LIB-007", "Libros", {"titulo": "Física universitaria", "autor": "Sears y Zemansky",
                           "isbn": "9786073244398", "editorial": "Pearson", "anio": 2018}),
    ("EQP-001", "Equipos", {"nombre": "Laptop", "marca": "Lenovo", "modelo": "ThinkPad E14",
                            "numero_serie": "LNV-2026-001"}),
    ("EQP-002", "Equipos", {"nombre": "Proyector", "marca": "Epson", "modelo": "PowerLite X49",
                            "numero_serie": "EPS-2026-014"}),
    ("EQP-003", "Equipos", {"nombre": "Cámara", "marca": "Canon", "modelo": "EOS Rebel T7",
                            "numero_serie": "CAN-2026-007"}),
    ("EQP-004", "Equipos", {"nombre": "Tablet", "marca": "Samsung", "modelo": "Galaxy Tab A9",
                            "numero_serie": "SMG-2026-021"}),
    ("EQP-005", "Equipos", {"nombre": "Laptop", "marca": "HP", "modelo": "ProBook 440",
                            "numero_serie": "HP-2026-033"}),
    ("EQP-006", "Equipos", {"nombre": "Micrófono inalámbrico", "marca": "Shure", "modelo": "BLX24",
                            "numero_serie": "SHR-2026-005"}),
    ("EQP-007", "Equipos", {"nombre": "Kit Arduino", "marca": "Arduino", "modelo": "Uno R3",
                            "numero_serie": "ARD-2026-012"}),
    ("IND-001", "Indumentaria", {"prenda": "Mandil de laboratorio", "talla": "S", "color": "Blanco"}),
    ("IND-002", "Indumentaria", {"prenda": "Mandil de laboratorio", "talla": "M", "color": "Blanco"}),
    ("IND-003", "Indumentaria", {"prenda": "Mandil de laboratorio", "talla": "L", "color": "Blanco"}),
    ("IND-004", "Indumentaria", {"prenda": "Casco de seguridad", "talla": "M", "color": "Amarillo"}),
    ("IND-005", "Indumentaria", {"prenda": "Lentes de protección", "talla": "M", "color": "Transparente"}),
    ("IND-006", "Indumentaria", {"prenda": "Chaleco reflectivo", "talla": "L", "color": "Naranja"}),
]

# Préstamos ACTIVOS de hoy: ítem, (tipo de solicitante, n.º), minutos desde la entrega, horas
ACTIVOS = [
    ("LIB-005", (TipoUsuario.ALUMNO, 0), 30, 3),
    ("LIB-006", (TipoUsuario.ALUMNO, 1), 20, 3),
    ("EQP-004", (TipoUsuario.DOCENTE, 1), 40, 2),   # Equipos es especial: lo aprobó el supervisor
    ("IND-002", (TipoUsuario.ALUMNO, 2), 10, 3),
    ("IND-005", (TipoUsuario.ADMINISTRATIVO, 0), 25, 2),
]

# Préstamos DEVUELTOS: ítem, solicitante, días hábiles atrás, hora de entrega, horas, minutos de atraso
DEVUELTOS = [
    ("LIB-001", (TipoUsuario.ALUMNO, 3), 2, 9, 3, 0),
    ("LIB-002", (TipoUsuario.ALUMNO, 4), 3, 10, 2, 0),
    ("LIB-001", (TipoUsuario.ALUMNO, 0), 5, 14, 3, 40),
    ("EQP-001", (TipoUsuario.DOCENTE, 2), 4, 8, 3, 0),
    ("EQP-002", (TipoUsuario.DOCENTE, 3), 6, 15, 2, 0),
    ("EQP-001", (TipoUsuario.ALUMNO, 5), 8, 11, 2, 75),
    ("IND-001", (TipoUsuario.ALUMNO, 6), 7, 9, 4, 0),
    ("IND-004", (TipoUsuario.ADMINISTRATIVO, 1), 9, 13, 3, 0),
    ("LIB-003", (TipoUsuario.ALUMNO, 1), 10, 10, 3, 0),
    ("EQP-003", (TipoUsuario.DOCENTE, 4), 12, 9, 2, 20),
]


class Command(BaseCommand):
    help = "Carga los datos de la revisión/entrega: cuentas del curso, 20 ítems, políticas y préstamos."
    stealth_options = ("ahora",)   # solo para las pruebas: fija la hora "actual"

    def handle(self, *args, **opciones):
        self.ahora = timezone.localtime(opciones.get("ahora") or timezone.now())
        self.horario = HorarioAtencion.desde_settings()

        call_command("seed_unsa", stdout=self.stdout)
        with transaction.atomic():
            self._personas()
            self.items = self._catalogo()
            self._politicas()
            devueltos = self._devueltos()
            activos = self._activos()

        self.stdout.write(self.style.SUCCESS(
            f"\nDatos de la entrega listos: {len(ITEMS)} ítems · {activos} préstamos activos hoy · "
            f"{devueltos} préstamos devueltos nuevos."))

    # ------------------------------------------------------------------ personas
    def _personas(self):
        """Personal (por su rol) y solicitantes por tipo. El encargado y el supervisor no
        reciben préstamos de ejemplo: no se entregan ni se aprueban préstamos a sí mismos."""
        def con_rol(rol):
            return Cuenta.objects.filter(roles__contains=[rol]).order_by("correo").first()

        self.encargado = con_rol(RolSistema.ENCARGADO)
        self.supervisor = con_rol(RolSistema.SUPERVISOR)
        personal = [RolSistema.ENCARGADO, RolSistema.SUPERVISOR]
        self.solicitantes = {}
        for tipo in TipoUsuario.values:
            cuentas = [
                p.cuenta for p in PerfilSolicitante.objects.filter(tipo=tipo, habilitado_institucional=True)
                .select_related("cuenta").order_by("cuenta__nombres")
                if not any(r in p.cuenta.roles for r in personal)
            ]
            self.solicitantes[tipo] = cuentas

    def _quien(self, clave):
        tipo, n = clave
        cuentas = self.solicitantes[tipo]
        return cuentas[n % len(cuentas)]

    # ------------------------------------------------------------------ catálogo y políticas
    def _catalogo(self):
        categorias = {}
        for nombre, datos in CATEGORIAS.items():
            categoria, _ = Categoria.objects.update_or_create(nombre=nombre, defaults=datos)
            categorias[nombre] = categoria
        items = {}
        for codigo, categoria, atributos in ITEMS:
            item = Item.objects.filter(codigo=codigo).first() or Item(codigo=codigo, estado=EstadoItem.DISPONIBLE)
            item.categoria = categorias[categoria]
            item.atributos = atributos
            item.full_clean()   # valida los atributos contra su categoría
            item.save()
            items[codigo] = item
        return items

    def _politicas(self):
        from apps.politicas.aplicacion.dtos import PoliticaDTO
        from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
        from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl

        servicio = PoliticaServicioAplicacion(PoliticaRepositorioImpl())
        categorias = {c.nombre: c.id for c in Categoria.objects.all()}
        for (nombre, tipo), (horas, renov, antelacion, global_, por_tipo) in POLITICAS.items():
            servicio.configurar(PoliticaDTO(
                tipo_item=nombre, tipo_usuario=tipo, categoria_id=categorias[nombre],
                duracion_maxima=horas, max_renovaciones=renov, antelacion_reserva=antelacion,
                limite_simultaneo_global=global_, limite_simultaneo_por_tipo=por_tipo,
            ))

    # ------------------------------------------------------------------ préstamos
    def _momento(self, dia, hora, minuto=0):
        return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))

    def _dia_habil_atras(self, dias):
        dia, restantes = self.ahora.date(), dias
        while restantes:
            dia -= timedelta(days=1)
            if self.horario.atiende(dia):
                restantes -= 1
        return dia

    def _prestar(self, item, solicitante, entrega, vence, devuelto=None):
        """Crea la reserva y el préstamo como lo dejaría el flujo real (entrega y devolución)."""
        reserva = Reserva.objects.create(
            item_id=item.id, categoria_id=item.categoria_id, solicitante_id=solicitante.pk,
            fecha=timezone.localtime(entrega).date(),
            hora_inicio=timezone.localtime(entrega).time(), hora_fin=timezone.localtime(vence).time(),
            finalidad="Uso en clase",
            estado=EstadoReserva.FINALIZADA if devuelto else EstadoReserva.ATENDIDA,
            aprobado_por_supervisor_id=self.supervisor.pk if item.categoria.es_especial else None,
        )
        alumno = solicitante.perfil.tipo == TipoUsuario.ALUMNO
        prestamo = Prestamo.objects.create(
            item_id=item.id, solicitante_id=solicitante.pk, reserva_id=reserva.id,
            encargado_entrega_id=self.encargado.pk,
            encargado_devolucion_id=self.encargado.pk if devuelto else None,
            garantia_tipo=TipoGarantia.CARNE_UNIVERSITARIO if alumno else TipoGarantia.DNI,
            garantia_devuelta=bool(devuelto), terminos_aceptados=True,
            fecha_entrega=entrega, fecha_vencimiento=vence, fecha_devolucion_real=devuelto,
            estado=EstadoPrestamo.DEVUELTO if devuelto else EstadoPrestamo.ACTIVO,
        )
        CondicionFisica.objects.create(
            item=item, prestamo_id=prestamo.id, responsable_id=self.encargado.pk, momento="ENTREGA",
            fecha=timezone.localtime(entrega).date(), descripcion="En buen estado, completo.",
        )
        if devuelto:
            CondicionFisica.objects.create(
                item=item, prestamo_id=prestamo.id, responsable_id=self.encargado.pk, momento="DEVOLUCION",
                fecha=timezone.localtime(devuelto).date(), descripcion="Devuelto en buen estado.",
            )
        return prestamo

    def _devueltos(self):
        creados = 0
        for codigo, quien, dias, hora, horas, atraso in DEVUELTOS:
            item, solicitante = self.items[codigo], self._quien(quien)
            dia = self._dia_habil_atras(dias)
            entrega = self._momento(dia, hora)
            if Prestamo.objects.filter(item_id=item.id, fecha_entrega=entrega).exists():
                continue   # ya estaba: no se duplica
            vence = entrega + timedelta(hours=horas)
            devuelto = vence + timedelta(minutes=atraso) if atraso else vence - timedelta(minutes=10)
            prestamo = self._prestar(item, solicitante, entrega, vence, devuelto)
            creados += 1
            if atraso >= 60:   # un atraso largo deja una observación
                Sancion.objects.get_or_create(
                    solicitante_id=solicitante.pk, prestamo_id=prestamo.pk,
                    defaults=dict(aplicada_por_id=self.encargado.pk, tipo=TipoSancion.OBSERVACION,
                                  motivo=f"Devolvió {codigo} con {atraso} min de atraso.", fecha_inicio=dia),
                )
        return creados

    def _activos(self):
        hoy = self.ahora.date()
        apertura = self._momento(hoy, self.horario.apertura.hour, self.horario.apertura.minute)
        cierre = self._momento(hoy, self.horario.cierre.hour, self.horario.cierre.minute)
        en_horario = self.horario.atiende(hoy) and apertura <= self.ahora <= cierre - timedelta(hours=1)
        vigentes = 0
        for codigo, quien, hace_min, horas in ACTIVOS:
            item = self.items[codigo]
            abierto = Prestamo.objects.filter(
                item_id=item.id, estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO]).first()
            if abierto and abierto.fecha_vencimiento > self.ahora:
                vigentes += 1          # ya hay uno activo de hoy: se deja como está
                continue
            if abierto:                # quedó de otro día: se cierra como devuelto
                self._cerrar(abierto)
            if not en_horario:
                continue
            entrega = max(apertura, self.ahora - timedelta(minutes=hace_min)).replace(second=0, microsecond=0)
            vence = min(cierre, entrega + timedelta(hours=horas))
            self._prestar(item, self._quien(quien), entrega, vence)
            item.estado = EstadoItem.PRESTADO
            item.save(update_fields=["estado", "actualizado_en"])
            vigentes += 1
        if not en_horario:
            self.stdout.write(self.style.WARNING(
                "Fuera del horario de atención (lunes a viernes de 08:00 a 19:00): no se crearon los "
                "préstamos activos de hoy. Corre de nuevo `seed_entrega` en horario de atención."))
        return vigentes

    def _cerrar(self, prestamo):
        prestamo.estado = EstadoPrestamo.DEVUELTO
        prestamo.fecha_devolucion_real = prestamo.fecha_vencimiento - timedelta(minutes=10)
        prestamo.encargado_devolucion_id = self.encargado.pk
        prestamo.garantia_devuelta = True
        prestamo.save()
        Reserva.objects.filter(pk=prestamo.reserva_id).update(estado=EstadoReserva.FINALIZADA)
        Item.objects.filter(pk=prestamo.item_id).update(estado=EstadoItem.DISPONIBLE)
