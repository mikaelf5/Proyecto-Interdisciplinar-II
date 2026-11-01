from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    # Solicitante
    path("mias/", views.MisReservasView.as_view(), name="mias"),
    path("item/<uuid:item_id>/reservar/", views.ReservarView.as_view(), name="reservar"),
    path("<uuid:pk>/cancelar/", views.CancelarView.as_view(), name="cancelar"),
    # Consulta
    path("item/<uuid:item_id>/agenda/", views.AgendaView.as_view(), name="agenda"),
    # Encargado
    path("<uuid:pk>/anular/", views.AnularView.as_view(), name="anular"),
    # Supervisor
    path("supervisor/", views.BandejaSupervisorView.as_view(), name="bandeja_supervisor"),
    path("<uuid:pk>/aprobar/", views.AprobarSupervisorView.as_view(), name="aprobar"),
    path("<uuid:pk>/rechazar/", views.RechazarSupervisorView.as_view(), name="rechazar"),
]
