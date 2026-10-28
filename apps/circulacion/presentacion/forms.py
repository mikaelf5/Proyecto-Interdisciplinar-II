from django import forms

from apps.circulacion.models import Solicitud


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial.get("item_id"):
            self.fields["item_id"].widget = forms.HiddenInput()
            self.fields["categoria_id"].widget = forms.HiddenInput()