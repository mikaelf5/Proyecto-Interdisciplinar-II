# Datos de prueba para ver los 5 reportes con información.
# Respetan las reglas del sistema: cada préstamo dura UN día, de lunes a viernes,
# dentro del horario de atención (08:00–20:00) y de 2 a 4 horas; los ítems no salen
# de la universidad.
#
# Uso (cualquier consola):
#   python manage.py shell -c "exec(open('datos_reportes.py', encoding='utf-8').read())"
#
# OJO: borra TODOS los préstamos, sanciones, casos de pérdida y reportes antes de
# crear los de prueba. Úsalo solo en tu base local: con DEBUG=False se niega a correr.
#
# Deja los ítems coherentes con los préstamos: el que está en curso o vencido queda
# PRESTADO, el perdido queda de BAJA y los demás vuelven a DISPONIBLE.
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.auditoria.dominio.models import RegistroAuditoria
from apps.catalogo.models import Item
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoItem, EstadoPrestamo, TipoGarantia
from apps.perdidas.dominio.models import CasoPerdida
from apps.reportes.dominio.models import Reporte, TipoReporte
from apps.sanciones.dominio.models import Sancion, TipoSancion

if not settings.DEBUG:
    raise SystemExit("datos_reportes.py borra datos: solo se usa en local (DEBUG=True).")

MOTIVO_DANIO = "Carcasa rajada, detectada al revisarlo en la devolución"

U = get_user_model()
admin = U.objects.get(correo="admin@demo.pe")
enc = U.objects.get(correo="encargado@demo.pe")
ana = U.objects.get(correo="ana@demo.pe")
diego = U.objects.get(correo="diego@demo.pe")
# Pedro no se usa: su cuenta aún no está habilitada, así que no puede tener préstamos.
i = list(Item.objects.order_by("codigo")[:6])
if len(i) < 6:
    raise SystemExit("Faltan ítems: corre primero  python manage.py seed_demo")
COSTO_POR_CATEGORIA = {"Equipos": Decimal("2500.00"), "Libros": Decimal("120.00"),
                       "Indumentaria": Decimal("60.00")}

Prestamo.objects.all().delete()
Sancion.objects.all().delete()
CasoPerdida.objects.all().delete()
Reporte.objects.all().delete()
RegistroAuditoria.objects.filter(accion="ITEM_DANIADO", motivo__startswith="[prueba]").delete()  # versión anterior
RegistroAuditoria.objects.filter(accion="ITEM_DANIADO", motivo=MOTIVO_DANIO).delete()
RegistroAuditoria.objects.filter(accion="ITEM_DANIADO", motivo="Pantalla rayada al devolver").delete()  # del script anterior


def dia_habil(dias_atras):
    """Fecha de hace `dias_atras` días, corrida al viernes anterior si cae en fin de semana."""
    d = timezone.localdate() - timedelta(days=dias_atras)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def momento(fecha, hora, minuto=0):
    return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))


def prestamo(item, quien, dias_atras, entrega_h, duracion_h, devuelto_min=None,
             estado=EstadoPrestamo.DEVUELTO):
    """devuelto_min: minutos después de la entrega en que se devolvió (None = no se devolvió)."""
    fecha = dia_habil(dias_atras)
    entrega = momento(fecha, entrega_h)
    vence = entrega + timedelta(hours=duracion_h)
    devuelto = entrega + timedelta(minutes=devuelto_min) if devuelto_min is not None else None
    return Prestamo.objects.create(
        item_id=item.id, solicitante_id=quien.pk, reserva_id=uuid.uuid4(),
        encargado_entrega_id=enc.pk,
        encargado_devolucion_id=enc.pk if devuelto else None,
        garantia_tipo=TipoGarantia.CARNE_UNIVERSITARIO, garantia_devuelta=devuelto is not None,
        fecha_entrega=entrega, fecha_vencimiento=vence, fecha_devolucion_real=devuelto,
        estado=estado, terminos_aceptados=True,
    )


# ítem, solicitante, hace N días, hora de entrega, duración (h), devuelto a los X min
prestamo(i[0], ana,   20,  9, 3, 150)    # a tiempo
prestamo(i[0], diego, 18, 10, 3, 220)    # 40 min tarde -> observación
prestamo(i[1], ana,   15,  8, 2, 110)    # a tiempo
perdido = prestamo(i[3], diego, 14, 9, 4, None, EstadoPrestamo.CERRADO_POR_PERDIDA)
prestamo(i[0], ana,   10, 14, 3, 175)    # a tiempo
devuelto_daniado = prestamo(i[1], ana, 8, 15, 2, 195)    # 1 h 15 min tarde y con daño
prestamo(i[2], diego,  6, 11, 4, 230)    # a tiempo (su suspensión ya terminó)
prestamo(i[5], diego,  5, 16, 3, None, EstadoPrestamo.VENCIDO)  # no lo devolvió al cierre

# Uno en curso: entregado hace 30 min y vence en 2 h (solo tiene sentido en horario de atención).
ahora = timezone.localtime()
Prestamo.objects.create(
    item_id=i[4].id, solicitante_id=ana.pk, reserva_id=uuid.uuid4(), encargado_entrega_id=enc.pk,
    garantia_tipo=TipoGarantia.CARNE_UNIVERSITARIO,
    fecha_entrega=ahora - timedelta(minutes=30), fecha_vencimiento=ahora + timedelta(hours=2),
    estado=EstadoPrestamo.ACTIVO, terminos_aceptados=True,
)

Sancion.objects.create(
    solicitante_id=diego.pk, aplicada_por_id=enc.pk, tipo=TipoSancion.OBSERVACION,
    motivo="Devolvió el ítem con 40 min de atraso", fecha_inicio=dia_habil(18),
)
Sancion.objects.create(
    solicitante_id=diego.pk, aplicada_por_id=enc.pk, tipo=TipoSancion.SUSPENSION_TEMPORAL,
    motivo=f"Pérdida del ítem {i[3].codigo}", duracion_dias=5, fecha_inicio=dia_habil(14),
)

CasoPerdida.objects.create(
    prestamo_id=perdido.id, solicitante_id=diego.pk, fecha=dia_habil(14),
    observaciones="No lo devolvió al cierre; se buscó en el laboratorio y en el aula 204 sin encontrarlo",
    costo_estimado=COSTO_POR_CATEGORIA.get(i[3].categoria.nombre, Decimal("100.00")),
)

# Daño registrado al recibir el ítem en la devolución (como lo hace Circulación).
danio = RegistroAuditoria.objects.create(
    actor_id=enc.pk, accion="ITEM_DANIADO", entidad="Item", entidad_id=i[1].id,
    motivo=MOTIVO_DANIO,
)
RegistroAuditoria.objects.filter(pk=danio.pk).update(  # fecha_hora es auto_now_add
    fecha_hora=devuelto_daniado.fecha_devolucion_real + timedelta(minutes=2)
)

# Estados de los ítems coherentes con los préstamos (si no, el catálogo dejaría reservar
# un ítem que está prestado o perdido).
Item.objects.filter(pk__in=[x.id for x in i]).update(estado=EstadoItem.DISPONIBLE, motivo_fuera_servicio="")
Item.objects.filter(pk__in=[i[4].id, i[5].id]).update(estado=EstadoItem.PRESTADO)
Item.objects.filter(pk=i[3].id).update(estado=EstadoItem.BAJA, motivo_fuera_servicio="Perdido (caso de pérdida)")

inicio, fin = timezone.localdate() - timedelta(days=30), timezone.localdate()
for tipo in TipoReporte.values:
    Reporte.objects.create(tipo=tipo, periodo_inicio=inicio, periodo_fin=fin, generado_por_id=admin.pk)

print("Listo:", Prestamo.objects.count(), "préstamos,", Sancion.objects.count(), "sanciones,",
      CasoPerdida.objects.count(), "pérdida,", Reporte.objects.count(), "reportes")
