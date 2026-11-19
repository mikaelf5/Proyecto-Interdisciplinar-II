"""Lo que Sanciones necesita saber de otros módulos, pedido a sus servicios (no a sus tablas).

- Identidad: qué cuentas tienen el rol Solicitante, con su nombre, DNI y CUI.
- Circulación y Catálogo: los préstamos recientes de cada solicitante, para elegir el
  préstamo que originó la sanción por su fecha e ítem (y no escribiendo su ID).

Los imports van dentro de las funciones para no crear ciclos entre módulos.
"""
from datetime import timedelta

from django.utils import timezone

from apps.common.choices import RolSistema

DIAS_PRESTAMOS_RECIENTES = 365


def _cuentas():
    from apps.identidad.fabrica import cuenta_servicio
    return cuenta_servicio()


def _cui(cuenta):
    try:
        return cuenta.perfil.cui or ""
    except Exception:   # la cuenta no tiene perfil de solicitante
        return ""


def etiqueta_persona(cuenta):
    """'Ana Alumna · DNI 79000002 · CUI 20230001'"""
    partes = [cuenta.nombres, f"DNI {cuenta.dni}"]
    if _cui(cuenta):
        partes.append(f"CUI {_cui(cuenta)}")
    return " · ".join(partes)


def solicitantes(q=""):
    """Cuentas con rol Solicitante (opcionalmente filtradas por nombre, correo, DNI o CUI)."""
    return list(_cuentas().listar_cuentas(q, rol=RolSistema.SOLICITANTE))


def ids_que_coinciden(q):
    """IDs de las cuentas cuyo nombre, correo, DNI o CUI contiene el texto (cualquier rol)."""
    return {c.pk for c in _cuentas().listar_cuentas(q)}


def personas(ids):
    """{cuenta_id: (nombres, dni)} para mostrar nombres en vez de IDs."""
    from django.contrib.auth import get_user_model   # API pública de Django
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {c.pk: (c.nombres, c.dni) for c in get_user_model().objects.filter(pk__in=ids)}


def prestamos_recientes(incluir=()):
    """[(prestamo_id, solicitante_id, etiqueta)] del último año, más los de `incluir`.

    La etiqueta es "29/10/2026 · EQP-001 Laptop · Devuelto".
    """
    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    from apps.circulacion.aplicacion.servicios import PrestamoServicioAplicacion
    from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl

    servicio = PrestamoServicioAplicacion(PrestamoRepositorioImpl())
    hoy = timezone.localdate()
    prestamos = {p.id: p for p in servicio.entregados_entre(hoy - timedelta(days=DIAS_PRESTAMOS_RECIENTES), hoy)}
    for prestamo_id in incluir:
        if prestamo_id and prestamo_id not in prestamos:
            p = servicio.obtener(prestamo_id)
            if p:
                prestamos[p.id] = p
    items = CatalogoServicioAplicacion().obtener_items({p.item_id for p in prestamos.values()})
    estados = dict(_estados_prestamo())
    resultado = []
    for p in sorted(prestamos.values(), key=lambda p: p.fecha_entrega, reverse=True):
        item = items.get(p.item_id)
        que = f"{item.codigo} {item.nombre}" if item else str(p.item_id)[:8]
        cuando = timezone.localtime(p.fecha_entrega).strftime("%d/%m/%Y")
        resultado.append((p.id, p.solicitante_id, f"{cuando} · {que} · {estados.get(p.estado, p.estado)}"))
    return resultado


def _estados_prestamo():
    from apps.common.choices import EstadoPrestamo
    return EstadoPrestamo.choices
