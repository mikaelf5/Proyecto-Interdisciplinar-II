from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.BuscarView.as_view(), name="buscar"),
    path("nuevo/", views.RegistrarItemView.as_view(), name="registrar"),
    path("<uuid:pk>/", views.DetalleView.as_view(), name="detalle"),
    path("<uuid:pk>/editar/", views.EditarItemView.as_view(), name="editar"),
    path("<uuid:pk>/disponible/", views.PonerDisponibleView.as_view(), name="poner_disponible"),
    path("<uuid:pk>/daniado/", views.MarcarDaniadoView.as_view(), name="marcar_daniado"),
    path("<uuid:pk>/baja/", views.DarDeBajaView.as_view(), name="dar_de_baja"),
]
