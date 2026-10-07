from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import Cuenta, PerfilSolicitante


class CuentaCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    class Meta:
        model = Cuenta
        fields = ("correo", "nombres", "dni")

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return p2

    def save(self, commit=True):
        cuenta = super().save(commit=False)
        cuenta.set_password(self.cleaned_data["password1"])
        if commit:
            cuenta.save()
        return cuenta


class CuentaChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Contraseña")

    class Meta:
        model = Cuenta
        fields = (
            "correo", "nombres", "dni", "celular", "direccion", "roles",
            "is_active", "is_staff", "is_superuser", "groups", "user_permissions",
        )


@admin.register(Cuenta)
class CuentaAdmin(UserAdmin):
    add_form = CuentaCreationForm
    form = CuentaChangeForm
    model = Cuenta
    list_display = ("correo", "nombres", "dni", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("correo", "nombres", "dni")
    ordering = ("correo",)
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos personales", {"fields": ("nombres", "dni", "celular", "direccion")}),
        ("Roles del dominio", {"fields": ("roles",)}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("correo", "nombres", "dni", "password1", "password2")}),
    )


@admin.register(PerfilSolicitante)
class PerfilSolicitanteAdmin(admin.ModelAdmin):
    list_display = ("cuenta", "tipo", "etiqueta", "habilitado_institucional")
    list_filter = ("tipo", "etiqueta", "habilitado_institucional")
    search_fields = ("cuenta__nombres", "cuenta__correo", "cui")
    autocomplete_fields = ("cuenta",)
    readonly_fields = ("id", "creado_en", "actualizado_en")
