from django import forms

from apps.common.choices import RolSistema


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
