from django import forms

from .models import Reporte


class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ["tipo", "periodo_inicio", "periodo_fin"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodo_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "periodo_fin": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("periodo_inicio"), datos.get("periodo_fin")
        if inicio and fin and fin < inicio:
            self.add_error("periodo_fin", "La fecha final no puede ser anterior a la inicial.")
        return datos
