from django import forms

from .models import Reporte


class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ["tipo", "periodo_inicio", "periodo_fin", "generado_por_id"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodo_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_fin": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "generado_por_id": forms.TextInput(attrs={"class": "form-control"}),
        }