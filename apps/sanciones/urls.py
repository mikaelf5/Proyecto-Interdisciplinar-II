from django.urls import path

from . import views

app_name = "sanciones"

urlpatterns = [
    path("", views.SancionListView.as_view(), name="lista"),
    path("nueva/", views.SancionCreateView.as_view(), name="crear"),
    path("solicitante/<uuid:solicitante_id>/", views.SancionHistorialView.as_view(), name="historial"),
    path("<uuid:pk>/editar/", views.SancionUpdateView.as_view(), name="editar"),
    path("<uuid:pk>/levantar/", views.SancionLevantarView.as_view(), name="levantar"),
    path("<uuid:pk>/eliminar/", views.SancionDeleteView.as_view(), name="eliminar"),
]
