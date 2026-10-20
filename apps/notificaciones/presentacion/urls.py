from django.urls import path

from . import views

app_name = "notificaciones"

urlpatterns = [
    path("", views.mis_notificaciones, name="mias"),
    path("<uuid:pk>/leida/", views.marcar_leida, name="marcar_leida"),
]
