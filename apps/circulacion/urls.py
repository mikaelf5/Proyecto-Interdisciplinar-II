from django.urls import path

from apps.circulacion.presentacion.views import (
    EntregasHoyView,
    RegistrarEntregaView,
    DevolucionesView,
    RegistrarDevolucionView,
    MisPrestamosView,
    RenovarPrestamoView,
    PrestamosVencidosView,
)

app_name = "circulacion"

urlpatterns = [
    # Entregas
    path("entregas/", EntregasHoyView.as_view(), name="entregas_hoy"),
    path(
        "entregas/<uuid:reserva_id>/registrar/",
        RegistrarEntregaView.as_view(),
        name="registrar_entrega",
    ),

    # Devoluciones
    path("devoluciones/", DevolucionesView.as_view(), name="devoluciones"),
    path(
        "devoluciones/<uuid:prestamo_id>/registrar/",
        RegistrarDevolucionView.as_view(),
        name="registrar_devolucion",
    ),

    # Historial y renovaciones
    path("mis-prestamos/", MisPrestamosView.as_view(), name="mis_prestamos"),
    path(
        "mis-prestamos/<uuid:prestamo_id>/renovar/",
        RenovarPrestamoView.as_view(),
        name="renovar_prestamo",
    ),

    # Préstamos vencidos
    path("vencidos/", PrestamosVencidosView.as_view(), name="prestamos_vencidos"),
]