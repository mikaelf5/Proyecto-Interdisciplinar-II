from django import forms


class ReservaForm(forms.Form):
    """Formulario de reserva: un día + rango de horas de ESE día."""
    fecha = forms.DateField(
        label="Día",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )
    hora_inicio = forms.TimeField(
        label="Desde",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control", "step": 900}, format="%H:%M"),
    )
    hora_fin = forms.TimeField(
        label="Hasta",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control", "step": 900}, format="%H:%M"),
    )
    finalidad = forms.CharField(
        label="Finalidad (opcional)", required=False, max_length=300,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control",
                                     "placeholder": "Ej.: exposición del curso de Redes"}),
    )

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("hora_inicio"), datos.get("hora_fin")
        if desde and hasta and hasta <= desde:
            self.add_error("hora_fin", "Debe ser posterior a la hora de inicio.")
        return datos


class MotivoForm(forms.Form):
    """Motivo obligatorio para rechazar (supervisor) o anular (encargado)."""
    motivo = forms.CharField(max_length=255, label="Motivo")
