from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.buscar, name="buscar"),
    path("<uuid:pk>/", views.detalle, name="detalle"),
    path("<uuid:pk>/disponible/", views.poner_disponible, name="poner_disponible"),
    path("<uuid:pk>/daniado/", views.marcar_daniado, name="marcar_daniado"),
    path("<uuid:pk>/baja/", views.dar_de_baja, name="dar_de_baja"),
]
