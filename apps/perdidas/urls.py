from django.urls import path

from . import views

app_name = "perdidas"

urlpatterns = [
    path("", views.CasoPerdidaListView.as_view(), name="lista"),
    path("nuevo/", views.CasoPerdidaCreateView.as_view(), name="crear"),
    path("<uuid:pk>/editar/", views.CasoPerdidaUpdateView.as_view(), name="editar"),
    path("<uuid:pk>/eliminar/", views.CasoPerdidaDeleteView.as_view(), name="eliminar"),
]