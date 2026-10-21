from django import forms

from .models import Sancion, TipoSancion


class SancionForm(forms.ModelForm):
    """Quién aplica la sanción y si está activa se manejan solos (no se piden)."""

    class Meta:
        model = Sancion
        fields = [
            "solicitante_id",
            "prestamo_id",
            "tipo",
            "motivo",
            "duracion_dias",
            "fecha_inicio",
        ]
        widgets = {
            "solicitante_id": forms.TextInput(attrs={"class": "form-control"}),
            "prestamo_id": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "duracion_dias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "fecha_inicio": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
        }
        help_texts = {
            "solicitante_id": "ID (UUID) del solicitante sancionado.",
            "prestamo_id": "Opcional: préstamo que originó la sanción.",
            "motivo": "Obligatorio: queda registrado también en la auditoría.",
            "duracion_dias": "Obligatorio para suspensión temporal; vacío = sin plazo.",
        }

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if len(motivo) < 5:
            raise forms.ValidationError("Describe el motivo (mínimo 5 caracteres).")
        return motivo

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        duracion = datos.get("duracion_dias")
        if tipo == TipoSancion.SUSPENSION_TEMPORAL and not duracion:
            self.add_error(
                "duracion_dias",
                "La suspensión temporal necesita una duración en días.",
            )
        return datos
