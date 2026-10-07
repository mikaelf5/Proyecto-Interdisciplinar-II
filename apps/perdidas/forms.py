from django import forms

from .models import CasoPerdida


class CasoPerdidaForm(forms.ModelForm):
    class Meta:
        model = CasoPerdida
        fields = ["prestamo_id", "solicitante_id", "fecha", "observaciones", "costo_estimado", "cerrado"]
        widgets = {
            "prestamo_id": forms.TextInput(attrs={"class": "form-control"}),
            "solicitante_id": forms.TextInput(attrs={"class": "form-control"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "costo_estimado": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cerrado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }