"""Capa de PRESENTACIÓN — ReservaController (PDF): crear, confirmar, cancelar, listaEspera."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..aplicacion.servicios import ReservaServicioAplicacion

solo_personal = user_passes_test(lambda u: u.is_staff)


def _servicio():
    return ReservaServicioAplicacion()


def _errores(e):
    return " ".join(e.messages) if hasattr(e, "messages") else str(e)


@login_required
@require_POST
def crear(request, item_id):
    try:
        r = _servicio().crear(item_id, request.user.id)
        messages.success(request, f"Reserva creada. Tu posición en la cola es la n.º {r.posicion_en_cola}.")
    except ValidationError as e:
        messages.error(request, _errores(e))
    return redirect("catalogo:detalle", pk=item_id)


@login_required
def lista_espera(request, item_id):
    from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
    try:
        item = CatalogoServicioAplicacion().obtener_item(item_id)
    except ValidationError as e:
        messages.error(request, _errores(e))
        return redirect("catalogo:buscar")
    return render(request, "reservas/lista_espera.html", {
        "item": item,
        "cola": _servicio().lista_espera(item_id),
    })


@login_required
def mis_reservas(request):
    return render(request, "reservas/mis_reservas.html", {
        "reservas": _servicio().mis_reservas(request.user.id),
    })


def _accion(request, funcion, ok):
    try:
        r = funcion()
        messages.success(request, ok)
        return r
    except ValidationError as e:
        messages.error(request, _errores(e))


@login_required
@solo_personal
@require_POST
def confirmar(request, pk):
    _accion(request, lambda: _servicio().confirmar(pk), "Reserva confirmada.")
    return redirect(request.POST.get("next") or "reservas:mias")


@login_required
@require_POST
def cancelar(request, pk):
    _accion(request, lambda: _servicio().cancelar(pk), "Reserva cancelada.")
    return redirect(request.POST.get("next") or "reservas:mias")


@login_required
@solo_personal
@require_POST
def asignar_siguiente(request, item_id):
    r = _accion(request, lambda: _servicio().asignar_siguiente(item_id),
                "Se confirmó al siguiente de la cola y se le notificó.")
    if r is None:
        messages.info(request, "No hay nadie en la cola.")
    return redirect("reservas:lista_espera", item_id=item_id)
