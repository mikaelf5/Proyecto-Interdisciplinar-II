"""Ayudantes de prueba compartidos por Sanciones, Pérdidas, Reportes y Auditoría."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalogo.aplicacion.dtos import NuevoItemDTO
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoPrestamo, RolSistema, TipoGarantia


def crear_cuenta(correo=None, nombres="Persona", roles=(RolSistema.ADMINISTRADOR,)):
    correo = correo or f"{uuid.uuid4().hex[:8]}@demo.pe"
    dni = str(uuid.uuid4().int)[:8]
    return get_user_model().objects.create_user(correo, nombres, dni, "clave123", roles=list(roles))


def crear_item(codigo="EQP-001", nombre="Laptop"):
    """Crea una categoría nueva y un ítem DISPONIBLE; devuelve el ItemDTO."""
    catalogo = CatalogoServicioAplicacion()
    categoria = catalogo.crear_categoria(f"Equipos {codigo}", definicion_atributos={
        "nombre": {"tipo": "texto", "requerido": True}})
    return catalogo.registrar_item(NuevoItemDTO(
        codigo=codigo, categoria_id=categoria.id, atributos={"nombre": nombre}))


def crear_prestamo(item_id, solicitante_id, estado=EstadoPrestamo.ACTIVO,
                   entrega=None, vence=None, devuelto=None):
    """Crea un Prestamo directo en la base. Se adapta si `solicitud_id` pasa a `reserva_id`."""
    ahora = timezone.now()
    entrega = entrega or ahora - timedelta(hours=2)
    campos = {f.name for f in Prestamo._meta.get_fields()}
    origen = "reserva_id" if "reserva_id" in campos else "solicitud_id"
    return Prestamo.objects.create(
        item_id=item_id, solicitante_id=solicitante_id, encargado_entrega_id=uuid.uuid4(),
        garantia_tipo=TipoGarantia.DNI, terminos_aceptados=True,
        fecha_entrega=entrega, fecha_vencimiento=vence or entrega + timedelta(hours=4),
        fecha_devolucion_real=devuelto, estado=estado, **{origen: uuid.uuid4()},
    )
