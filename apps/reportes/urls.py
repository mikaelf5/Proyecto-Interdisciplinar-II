from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.ReporteListView.as_view(), name="lista"),
    path("nuevo/", views.ReporteCreateView.as_view(), name="crear"),
    path("<uuid:pk>/editar/", views.ReporteUpdateView.as_view(), name="editar"),
    path("<uuid:pk>/eliminar/", views.ReporteDeleteView.as_view(), name="eliminar"),
    path("<uuid:pk>/exportar/<str:formato>/", views.exportar_reporte, name="exportar"),
]