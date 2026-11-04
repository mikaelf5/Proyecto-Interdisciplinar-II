from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .presentacion.auth_controller import AuthController, LogoutController
from .presentacion.cuenta_controller import (
    ActivarCuentaController,
    AsignarRolController,
    CompletarPerfilController,
    CuentaDetalleController,
    CuentaListController,
    DesactivarCuentaController,
    HabilitacionController,
    QuitarRolController,
    RecalcularEtiquetaController,
    RegistrarCuentaController,
)
from .presentacion.perfil_controller import MiPerfilController
from .presentacion.registro_controller import (
    AprobarSolicitudController,
    DocumentoSolicitudController,
    RechazarSolicitudController,
    RegistroEnviadoController,
    RegistroPublicoController,
    SolicitudDetalleController,
    SolicitudListController,
)

app_name = "identidad"

urlpatterns = [
    path("login/", AuthController.as_view(), name="login"),
    path("logout/", LogoutController.as_view(), name="logout"),
    path("mi-perfil/", MiPerfilController.as_view(), name="mi_perfil"),

    # --- Registro por autoservicio (público) ---
    path("registro/", RegistroPublicoController.as_view(), name="registro"),
    path("registro/enviado/", RegistroEnviadoController.as_view(), name="registro_enviado"),

    # --- RF-B4: recuperar contraseña con las vistas de Django (el correo sale en la consola) ---
    path("contrasena/recuperar/", auth_views.PasswordResetView.as_view(
        template_name="identidad/password_reset_form.html",
        email_template_name="identidad/password_reset_email.txt",
        subject_template_name="identidad/password_reset_subject.txt",
        success_url=reverse_lazy("identidad:password_reset_done"),
    ), name="password_reset"),
    path("contrasena/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(
        template_name="identidad/password_reset_done.html",
    ), name="password_reset_done"),
    path("contrasena/nueva/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="identidad/password_reset_confirm.html",
        success_url=reverse_lazy("identidad:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("contrasena/nueva/listo/", auth_views.PasswordResetCompleteView.as_view(
        template_name="identidad/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("contrasena/cambiar/", auth_views.PasswordChangeView.as_view(
        template_name="identidad/password_change_form.html",
        success_url=reverse_lazy("identidad:password_change_done"),
    ), name="password_change"),
    path("contrasena/cambiar/listo/", auth_views.PasswordChangeDoneView.as_view(
        template_name="identidad/password_change_done.html",
    ), name="password_change_done"),

    # --- Administrador: cuentas ---
    path("cuentas/", CuentaListController.as_view(), name="cuentas"),
    path("cuentas/nueva/", RegistrarCuentaController.as_view(), name="registrar"),
    path("cuentas/<uuid:pk>/", CuentaDetalleController.as_view(), name="cuenta_detalle"),
    path("cuentas/<uuid:pk>/rol/", AsignarRolController.as_view(), name="asignar_rol"),
    path("cuentas/<uuid:pk>/rol/quitar/", QuitarRolController.as_view(), name="quitar_rol"),
    path("cuentas/<uuid:pk>/desactivar/", DesactivarCuentaController.as_view(), name="desactivar"),
    path("cuentas/<uuid:pk>/activar/", ActivarCuentaController.as_view(), name="activar"),
    path("cuentas/<uuid:pk>/habilitacion/", HabilitacionController.as_view(), name="habilitacion"),
    path("cuentas/<uuid:pk>/perfil/", CompletarPerfilController.as_view(), name="completar_perfil"),
    # --- Administrador: solicitudes de registro ---
    path("solicitudes/", SolicitudListController.as_view(), name="solicitudes"),
    path("solicitudes/<uuid:pk>/", SolicitudDetalleController.as_view(), name="solicitud_detalle"),
    path("solicitudes/<uuid:pk>/aprobar/", AprobarSolicitudController.as_view(), name="aprobar_solicitud"),
    path("solicitudes/<uuid:pk>/rechazar/", RechazarSolicitudController.as_view(), name="rechazar_solicitud"),
    path("solicitudes/<uuid:pk>/documento/", DocumentoSolicitudController.as_view(), name="documento_solicitud"),
    path("cuentas/<uuid:pk>/etiqueta/", RecalcularEtiquetaController.as_view(), name="recalcular_etiqueta"),
]
