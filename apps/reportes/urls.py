from django.urls import path

from . import historiales_views as historiales
from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.ReporteListView.as_view(), name="lista"),
    path("nuevo/", views.ReporteCreateView.as_view(), name="crear"),
    path("<uuid:pk>/", views.ReporteDetailView.as_view(), name="detalle"),
    path("<uuid:pk>/eliminar/", views.ReporteDeleteView.as_view(), name="eliminar"),
    path("<uuid:pk>/exportar/<str:formato>/", views.exportar_reporte, name="exportar"),
    # Historiales
    path("historial/personas/", historiales.BuscarPersonaView.as_view(), name="historial_personas"),
    path("historial/personas/<uuid:cuenta_id>/", historiales.HistorialPersonaView.as_view(),
         name="historial_persona"),
    path("historial/personas/<uuid:cuenta_id>/exportar/<str:formato>/",
         historiales.exportar_historial_persona, name="exportar_historial_persona"),
    path("historial/items/", historiales.BuscarItemView.as_view(), name="historial_items"),
    path("historial/items/<uuid:item_id>/", historiales.HistorialItemView.as_view(), name="historial_item"),
    path("historial/items/<uuid:item_id>/exportar/<str:formato>/",
         historiales.exportar_historial_item, name="exportar_historial_item"),
]
