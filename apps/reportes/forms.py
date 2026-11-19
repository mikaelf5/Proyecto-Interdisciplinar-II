from django import forms
from django.utils import timezone

from .models import Reporte

MAX_DIAS_PERIODO = 366   # un año como máximo, para que el reporte se lea y cargue rápido


class ReporteForm(forms.ModelForm):
    """Quién genera el reporte se toma de la sesión (no se pide)."""

    class Meta:
        model = Reporte
        fields = ["tipo", "periodo_inicio", "periodo_fin"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodo_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "periodo_fin": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django muestra "- Select an option -" sin traducir: se pone el texto en español.
        self.fields["tipo"].choices = [("", "— Elige el tipo de reporte —")] + [
            c for c in self.fields["tipo"].choices if c[0]
        ]

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("periodo_inicio"), datos.get("periodo_fin")
        hoy = timezone.localdate()
        if inicio and inicio > hoy:
            self.add_error("periodo_inicio", "El periodo no puede empezar en el futuro.")
        if fin and fin > hoy:
            self.add_error("periodo_fin", "La fecha final no puede ser posterior a hoy.")
        if inicio and fin:
            if fin < inicio:
                self.add_error("periodo_fin", "La fecha final no puede ser anterior a la inicial.")
            elif (fin - inicio).days + 1 > MAX_DIAS_PERIODO:
                self.add_error("periodo_fin", f"El periodo puede abarcar como máximo {MAX_DIAS_PERIODO} días.")
        return datos
