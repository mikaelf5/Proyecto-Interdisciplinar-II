from django import forms

from apps.common.choices import EstadoItem


class FiltroItemForm(forms.Form):
    """Formulario de búsqueda del catálogo (no está ligado a un modelo)."""
    texto = forms.CharField(
        required=False, label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Código, título, autor, marca…", "class": "form-control"}),
    )
    categoria_id = forms.ChoiceField(required=False, label="Categoría",
                                     widget=forms.Select(attrs={"class": "form-select"}))
    estado = forms.ChoiceField(
        required=False, label="Estado",
        choices=[("", "Todos")] + list(EstadoItem.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, categorias=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria_id"].choices = [("", "Todas")] + [(str(c.id), c.nombre) for c in categorias]


class MotivoForm(forms.Form):
    motivo = forms.CharField(max_length=255, label="Motivo")
