from django.urls import path
from . import views

app_name = "circulacion"

urlpatterns = [
    path(
        "solicitudes/",
        views.SolicitudListView.as_view(),
        name="solicitudes"
    ),

    path(
        "solicitudes/nueva/",
        views.SolicitudCreateView.as_view(),
        name="solicitud_nueva"
    ),
    path(
        "solicitudes/<uuid:pk>/",
        views.SolicitudDetailView.as_view(),
        name="solicitud_detalle"
    ),
]