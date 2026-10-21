from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("mias/", views.mis_reservas, name="mias"),
    path("item/<uuid:item_id>/", views.lista_espera, name="lista_espera"),
    path("item/<uuid:item_id>/reservar/", views.crear, name="crear"),
    path("item/<uuid:item_id>/asignar-siguiente/", views.asignar_siguiente, name="asignar_siguiente"),
    path("<uuid:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("<uuid:pk>/cancelar/", views.cancelar, name="cancelar"),
]
