"""Capa de PRESENTACIÓN — NotificacionController (PDF): misNotificaciones, marcarLeida."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..aplicacion.servicios import NotificacionServicioAplicacion

notificaciones = NotificacionServicioAplicacion()


@login_required
def mis_notificaciones(request):
    lista = notificaciones.mis_notificaciones(request.user.id)
    return render(request, "notificaciones/mis_notificaciones.html", {
        "notificaciones": lista,
        "sin_leer": sum(1 for n in lista if not n.leida),
    })


@login_required
@require_POST
def marcar_leida(request, pk):
    try:
        notificaciones.marcar_leida(pk, destinatario_id=request.user.id)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("notificaciones:mias")
