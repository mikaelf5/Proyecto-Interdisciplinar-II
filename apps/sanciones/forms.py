from django import forms

from .models import Sancion


class SancionForm(forms.ModelForm):
    class Meta:
        model = Sancion
        fields = [
            "solicitante_id",
            "aplicada_por_id",
            "prestamo_id",
            "tipo",
            "motivo",
            "duracion_dias",
            "fecha_inicio",
            "activa",
        ]
        widgets = {
            "solicitante_id": forms.TextInput(attrs={"class": "form-control"}),
            "aplicada_por_id": forms.TextInput(attrs={"class": "form-control"}),
            "prestamo_id": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "duracion_dias": forms.NumberInput(attrs={"class": "form-control"}),
            "fecha_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }