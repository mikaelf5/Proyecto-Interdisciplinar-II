from datetime import date

from django import forms

from .models import CasoPerdida


class CasoPerdidaForm(forms.ModelForm):
    """Un caso nuevo siempre empieza abierto; se cierra con el botón "Cerrar caso"."""

    class Meta:
        model = CasoPerdida
        fields = ["prestamo_id", "solicitante_id", "fecha", "observaciones", "costo_estimado"]
        widgets = {
            "prestamo_id": forms.TextInput(attrs={"class": "form-control"}),
            "solicitante_id": forms.TextInput(attrs={"class": "form-control"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "costo_estimado": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }
        help_texts = {
            "prestamo_id": "ID (UUID) del préstamo en el que se perdió el ítem.",
            "solicitante_id": "ID (UUID) del solicitante responsable.",
            "costo_estimado": "Opcional y solo informativo: el sistema no gestiona pagos.",
        }

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha > date.today():
            raise forms.ValidationError("La fecha no puede ser futura.")
        return fecha

    def clean_costo_estimado(self):
        costo = self.cleaned_data.get("costo_estimado")
        if costo is not None and costo < 0:
            raise forms.ValidationError("El costo no puede ser negativo.")
        return costo
