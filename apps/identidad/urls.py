from django.urls import path

from .presentacion.auth_controller import AuthController, LogoutController
from .presentacion.cuenta_controller import AsignarRolController, CuentaListController

app_name = "identidad"

urlpatterns = [
    path("login/", AuthController.as_view(), name="login"),
    path("logout/", LogoutController.as_view(), name="logout"),
    path("cuentas/", CuentaListController.as_view(), name="cuentas"),
    path("cuentas/<uuid:pk>/rol/", AsignarRolController.as_view(), name="asignar_rol"),
]
