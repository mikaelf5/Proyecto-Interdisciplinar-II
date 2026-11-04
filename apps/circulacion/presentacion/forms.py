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

class EntregaPrestamoForm(forms.Form):

    TIPOS_GARANTIA = [
        ("DNI", "DNI"),
        ("TARJETA", "Tarjeta"),
        ("OTRO", "Otro"),
    ]

    garantia_tipo = forms.ChoiceField(
        choices=TIPOS_GARANTIA,
        label="Tipo de garantía"
    )

    garantia_detalle = forms.CharField(
        required=False,
        label="Detalle de la garantía",
        widget=forms.TextInput(attrs={
            "placeholder": "Especificar si seleccionó Otro"
        })
    )

    terminos_aceptados = forms.BooleanField(
        required=True,
        label="Acepto los términos y condiciones"
    )

    descripcion_condicion = forms.CharField(
        label="Estado físico del artículo",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Describe el estado del artículo al momento de la entrega"
        })
    )
class DevolucionForm(forms.Form):

    descripcion_condicion = forms.CharField(
        label="Estado físico del artículo",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Describe el estado del artículo al momento de la devolución"
        })
    )

    garantia_devuelta = forms.BooleanField(
        required=False,
        label="Se devolvió la garantía al usuario"
    )

    item_daniado = forms.BooleanField(
        required=False,
        label="El artículo presenta daños"
    )
class RenovarPrestamoForm(forms.Form):
    nueva_hora_fin = forms.TimeField(
        label="Nueva hora de devolución",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={
                "type": "time",
                "class": "form-control",
                "required": True,
            }
        )
    )