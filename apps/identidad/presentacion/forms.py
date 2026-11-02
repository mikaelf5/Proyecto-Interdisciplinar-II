"""Formularios: validan el FORMATO (vacíos, dígitos, contraseñas iguales).

Las reglas de NEGOCIO (correo o DNI repetidos, acta, consentimiento) las
valida el servicio de aplicación; sus errores vuelven al campo correcto
gracias a `DatosInvalidos.errores`.
"""
from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.common.choices import RolSistema, TipoUsuario
from apps.identidad.dominio.documentos import ACTA_RESPONSABILIDAD, CONSENTIMIENTO_DATOS
from apps.identidad.dominio.validadores import validar_celular, validar_cui, validar_dni

CONTROL = {"class": "form-control"}
CHECK = {"class": "form-check-input"}


class LoginForm(forms.Form):
    correo = forms.EmailField(
        label="Correo institucional",
        widget=forms.EmailInput(attrs={
            "class": "form-control", "autofocus": True,
            "autocomplete": "email", "placeholder": "usuario@unsa.edu.pe",
        }),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "class": "form-control", "autocomplete": "current-password",
        }),
    )


class AsignarRolForm(forms.Form):
    rol = forms.ChoiceField(
        choices=RolSistema.choices,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )


class _PerfilCampos(forms.Form):
    """Campos del PerfilSolicitante (se reusan al registrar y al completar el perfil)."""

    tipo = forms.ChoiceField(
        label="Tipo de usuario", required=False,
        choices=[("", "— Elige —")] + list(TipoUsuario.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cui = forms.CharField(
        label="CUI", required=False, max_length=8, validators=[validar_cui],
        help_text="Código Único de Identificación (8 dígitos). Obligatorio para alumnos.",
        widget=forms.TextInput(attrs={**CONTROL, "inputmode": "numeric"}),
    )
    habilitado_institucional = forms.BooleanField(
        label="Habilitado por su condición institucional (matrícula o vínculo vigente)",
        required=False, widget=forms.CheckboxInput(attrs=CHECK),
    )
    acta_aceptada = forms.BooleanField(
        label="El solicitante firmó el acta de responsabilidad", required=False,
        help_text=ACTA_RESPONSABILIDAD, widget=forms.CheckboxInput(attrs=CHECK),
    )


class RegistroCuentaForm(_PerfilCampos):
    nombres = forms.CharField(label="Nombres y apellidos", max_length=150,
                              widget=forms.TextInput(attrs=CONTROL))
    dni = forms.CharField(label="DNI", max_length=8, validators=[validar_dni],
                          widget=forms.TextInput(attrs={**CONTROL, "inputmode": "numeric"}))
    correo = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs=CONTROL))
    celular = forms.CharField(label="Celular", max_length=9, required=False,
                              validators=[validar_celular],
                              widget=forms.TextInput(attrs={**CONTROL, "inputmode": "numeric"}))
    direccion = forms.CharField(label="Dirección", max_length=255, required=False,
                                widget=forms.TextInput(attrs=CONTROL))
    roles = forms.MultipleChoiceField(
        label="Roles", choices=RolSistema.choices, initial=[RolSistema.SOLICITANTE],
        widget=forms.CheckboxSelectMultiple(attrs=CHECK),
    )
    password1 = forms.CharField(
        label="Contraseña inicial", strip=False,
        help_text="Mínimo 8 caracteres, no solo números. El usuario puede cambiarla luego.",
        widget=forms.PasswordInput(attrs={**CONTROL, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Repite la contraseña", strip=False,
        widget=forms.PasswordInput(attrs={**CONTROL, "autocomplete": "new-password"}),
    )
    consentimiento_aceptado = forms.BooleanField(
        label="El usuario autorizó el tratamiento de sus datos personales (Ley N.° 29733)",
        required=False, help_text=CONSENTIMIENTO_DATOS, widget=forms.CheckboxInput(attrs=CHECK),
    )

    field_order = [
        "nombres", "dni", "correo", "celular", "direccion", "roles",
        "tipo", "cui", "habilitado_institucional", "acta_aceptada",
        "password1", "password2", "consentimiento_aceptado",
    ]

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return datos


class PerfilSolicitanteForm(_PerfilCampos):
    """Para una cuenta ya creada que aún no tiene perfil de solicitante."""


class ContactoForm(forms.Form):
    celular = forms.CharField(label="Celular", max_length=9, required=False,
                              validators=[validar_celular],
                              widget=forms.TextInput(attrs={**CONTROL, "inputmode": "numeric"}))
    direccion = forms.CharField(label="Dirección", max_length=255, required=False,
                                widget=forms.TextInput(attrs=CONTROL))


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo", required=False, max_length=500,
        widget=forms.TextInput(attrs={**CONTROL, "placeholder": "Motivo (obligatorio)"}),
    )
