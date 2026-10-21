from django.urls import path
from . import views
from .presentacion.views import (
    AprobarSolicitudView, AprobarSupervisorView,
    RechazarSolicitudView, CancelarSolicitudView,
)

app_name = "circulacion"

urlpatterns = [
    path("solicitudes/", views.SolicitudListView.as_view(), name="solicitudes"),
    path("solicitudes/nueva/", views.SolicitudCreateView.as_view(), name="solicitud_nueva"),
    path("solicitudes/<uuid:pk>/", views.SolicitudDetailView.as_view(), name="solicitud_detalle"),
    path("solicitudes/<uuid:pk>/aprobar/", AprobarSolicitudView.as_view(), name="solicitud_aprobar"),
    path("solicitudes/<uuid:pk>/aprobar-supervisor/", AprobarSupervisorView.as_view(), name="solicitud_aprobar_supervisor"),
    path("solicitudes/<uuid:pk>/rechazar/", RechazarSolicitudView.as_view(), name="solicitud_rechazar"),
    path("solicitudes/<uuid:pk>/cancelar/", CancelarSolicitudView.as_view(), name="solicitud_cancelar"),
]
