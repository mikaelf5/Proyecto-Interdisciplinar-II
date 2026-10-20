from django import forms

from .models import Solicitud


class SolicitudForm(forms.ModelForm):

    class Meta:
        model = Solicitud

        fields = [
            "item_id",
            "categoria_id",
            "fecha_inicio",
            "fecha_fin",
            "finalidad",
        ]

        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "finalidad": forms.Textarea(attrs={"rows": 3}),
        }